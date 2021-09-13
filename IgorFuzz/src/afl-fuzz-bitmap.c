/*
   american fuzzy lop++ - bitmap related routines
   ----------------------------------------------

   Originally written by Michal Zalewski

   Now maintained by Marc Heuse <mh@mh-sec.de>,
                        Heiko Eißfeldt <heiko.eissfeldt@hexco.de> and
                        Andrea Fioraldi <andreafioraldi@gmail.com>

   Copyright 2016, 2017 Google Inc. All rights reserved.
   Copyright 2019-2020 AFLplusplus Project. All rights reserved.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at:

     http://www.apache.org/licenses/LICENSE-2.0

   This is the real deal: the program takes an instrumented binary and
   attempts a variety of basic fuzzing tricks, paying close attention to
   how they affect the execution path.

 */

#include "afl-fuzz.h"
#include <limits.h>
#if !defined NAME_MAX
  #define NAME_MAX _XOPEN_NAME_MAX
#endif

u64 global_min_hit_count = UINT64_MAX;      /* The minimal sum of hits on edges for all cases */

u64 cur_hit_count;

u8 *trace_mini_ori;
u8 *original_virgin_bits;

/* Write bitmap to file. The bitmap is useful mostly for the secret
   -B option, to focus a separate fuzzing session on a particular
   interesting input without rediscovering all the others. */

void write_bitmap(afl_state_t *afl) {

  u8  fname[PATH_MAX];
  s32 fd;

  if (!afl->bitmap_changed) { return; }
  afl->bitmap_changed = 0;

  snprintf(fname, PATH_MAX, "%s/fuzz_bitmap", afl->out_dir);
  fd = open(fname, O_WRONLY | O_CREAT | O_TRUNC, 0600);

  if (fd < 0) { PFATAL("Unable to open '%s'", fname); }

  ck_write(fd, afl->virgin_bits, afl->fsrv.map_size, fname);

  close(fd);

}

/* Count the number of bits set in the provided bitmap. Used for the status
   screen several times every second, does not have to be fast. */

u32 count_bits(afl_state_t *afl, u8 *mem) {

  u32 *ptr = (u32 *)mem;
  u32  i = (afl->fsrv.map_size >> 2);
  u32  ret = 0;

  while (i--) {

    u32 v = *(ptr++);

    /* This gets called on the inverse, virgin bitmap; optimize for sparse
       data. */

    if (v == 0xffffffff) {

      ret += 32;
      continue;

    }

    v -= ((v >> 1) & 0x55555555);
    v = (v & 0x33333333) + ((v >> 2) & 0x33333333);
    ret += (((v + (v >> 4)) & 0xF0F0F0F) * 0x01010101) >> 24;

  }

  return ret;

}

/* Count the number of bytes set in the bitmap. Called fairly sporadically,
   mostly to update the status screen or calibrate and examine confirmed
   new paths. */

u32 count_bytes(afl_state_t *afl, u8 *mem) {

  u32 *ptr = (u32 *)mem;
  u32  i = (afl->fsrv.map_size >> 2);
  u32  ret = 0;

  while (i--) {

    u32 v = *(ptr++);

    if (!v) { continue; }
    if (v & 0x000000ffU) { ++ret; }
    if (v & 0x0000ff00U) { ++ret; }
    if (v & 0x00ff0000U) { ++ret; }
    if (v & 0xff000000U) { ++ret; }

  }

  return ret;

}

/* Count the number of non-255 bytes set in the bitmap. Used strictly for the
   status screen, several calls per second or so. */

u32 count_non_255_bytes(afl_state_t *afl, u8 *mem) {

  u32 *ptr = (u32 *)mem;
  u32  i = (afl->fsrv.map_size >> 2);
  u32  ret = 0;

  while (i--) {

    u32 v = *(ptr++);

    /* This is called on the virgin bitmap, so optimize for the most likely
       case. */

    if (v == 0xffffffffU) { continue; }
    if ((v & 0x000000ffU) != 0x000000ffU) { ++ret; }
    if ((v & 0x0000ff00U) != 0x0000ff00U) { ++ret; }
    if ((v & 0x00ff0000U) != 0x00ff0000U) { ++ret; }
    if ((v & 0xff000000U) != 0xff000000U) { ++ret; }

  }

  return ret;

}

/* Destructively simplify trace by eliminating hit count information
   and replacing it with 0x80 or 0x01 depending on whether the tuple
   is hit or not. Called on every new crash or timeout, should be
   reasonably fast. */
#define TIMES4(x) x, x, x, x
#define TIMES8(x) TIMES4(x), TIMES4(x)
#define TIMES16(x) TIMES8(x), TIMES8(x)
#define TIMES32(x) TIMES16(x), TIMES16(x)
#define TIMES64(x) TIMES32(x), TIMES32(x)
#define TIMES255(x)                                                      \
  TIMES64(x), TIMES64(x), TIMES64(x), TIMES32(x), TIMES16(x), TIMES8(x), \
      TIMES4(x), x, x, x
const u8 simplify_lookup[256] = {

    [0] = 1, [1] = TIMES255(128)

};

/* Destructively classify execution counts in a trace. This is used as a
   preprocessing step for any newly acquired traces. Called on every exec,
   must be fast. */

const u8 count_class_lookup8[256] = {

    [0] = 0,
    [1] = 1,
    [2] = 2,
    [3] = 4,
    [4] = TIMES4(8),
    [8] = TIMES8(16),
    [16] = TIMES16(32),
    [32] = TIMES32(64),
    [128] = TIMES64(128)

};

#undef TIMES255
#undef TIMES64
#undef TIMES32
#undef TIMES16
#undef TIMES8
#undef TIMES4

u16 count_class_lookup16[65536];

void init_count_class16(void) {

  u32 b1, b2;

  for (b1 = 0; b1 < 256; b1++) {

    for (b2 = 0; b2 < 256; b2++) {

      count_class_lookup16[(b1 << 8) + b2] =
          (count_class_lookup8[b1] << 8) | count_class_lookup8[b2];

    }

  }

}

/* Import coverage processing routines. */

#ifdef WORD_SIZE_64
  #include "coverage-64.h"
#else
  #include "coverage-32.h"
#endif

/* Check if the current execution path brings anything new to the table.
   Update virgin bits to reflect the finds. Returns 1 if the only change is
   the hit-count for a particular tuple; 2 if there are new tuples seen.
   Updates the map, so subsequent calls will always return 0.

   This function is called after every exec() on a fairly large buffer, so
   it needs to be fast. We do this in 32-bit and 64-bit flavors. */

inline u8 has_new_bits(afl_state_t *afl, u8 *virgin_map) {

#ifdef WORD_SIZE_64

  u64 *current = (u64 *)afl->fsrv.trace_bits;
  u64 *virgin = (u64 *)virgin_map;

  u32 i = (afl->fsrv.map_size >> 3);

#else

  u32 *current = (u32 *)afl->fsrv.trace_bits;
  u32 *virgin = (u32 *)virgin_map;

  u32 i = (afl->fsrv.map_size >> 2);

#endif                                                     /* ^WORD_SIZE_64 */

  u8 ret = 0;

  while (i--) {

    if (unlikely(*current)) discover_word(&ret, current, virgin);

    current++;
    virgin++;

  }

  if (unlikely(ret) && likely(virgin_map == afl->virgin_bits))
    afl->bitmap_changed = 1;

  return ret;

}

/* A combination of classify_counts and has_new_bits. If 0 is returned, then the
 * trace bits are kept as-is. Otherwise, the trace bits are overwritten with
 * classified values.
 *
 * This accelerates the processing: in most cases, no interesting behavior
 * happen, and the trace bits will be discarded soon. This function optimizes
 * for such cases: one-pass scan on trace bits without modifying anything. Only
 * on rare cases it fall backs to the slow path: classify_counts() first, then
 * return has_new_bits(). */

inline u8 has_new_bits_unclassified(afl_state_t *afl, u8 *virgin_map) {

  /* Handle the hot path first: no new coverage */
  u8 *end = afl->fsrv.trace_bits + afl->fsrv.map_size;

#ifdef WORD_SIZE_64

  if (!skim((u64 *)virgin_map, (u64 *)afl->fsrv.trace_bits, (u64 *)end))
    return 0;

#else

  if (!skim((u32 *)virgin_map, (u32 *)afl->fsrv.trace_bits, (u32 *)end))
    return 0;

#endif                                                     /* ^WORD_SIZE_64 */
  classify_counts(&afl->fsrv);
  return has_new_bits(afl, virgin_map);

}

/* Check if the current execution path brings anything shorter to the table.
   Update virgin bits to reflect the finds. Returns 1 if the only change is
   the hit-count for a particular tuple; 2 if there are tuples disappear.
   Updates the map, so subsequent calls will always return 0.
   This function is called after every exec() on a fairly large buffer, so
   it needs to be fast. We do this in 32-bit and 64-bit flavors.
   ret == 1 ----> we detect different hit count on certain edge
   ret == 2 ----> we detect coverage increase
   ret == 3 ----> we detect coverage decrease
   ret == 4 ----> we detect bitmap_size decrease
   */

inline u8 has_few_bits(afl_state_t *afl, u8* virgin_map) {
    u8 bms_decrease = 0; // whether bitmap size gets decreased
    u8 cov_decrease = 0; // whether at least one edge is no longer hit in current seed
    u8 hcn_decrease = 0; // whether the total hit counts gets decreased

#ifdef WORD_SIZE_64

    u64* current = (u64*)afl->fsrv.trace_bits;
    u64* virgin  = (u64*)virgin_map;

    u32  i =  (afl->fsrv.map_size >> 3);

#else

    u32* current = (u32*)afl->fsrv.trace_bits;
    u32* virgin  = (u32*)virgin_map;

    u32  i =  (afl->fsrv.map_size >> 2);

#endif /* ^WORD_SIZE_64 */

    u8   ret = 0;

    // initialize virgin_bits & total_min_bitmap_size & global_min_hit_count
    if (unlikely(afl->total_min_bitmap_size == 0) && unlikely(global_min_hit_count + 1 == 0x0)) {
        /* Initialize total_min_bitmap_size */
        u64 cur_bitmap_size;

        // initialize total_min_bitmap_size with cur_bitmap_size
        cur_bitmap_size = count_bytes(afl, afl->fsrv.trace_bits);
        afl->total_min_bitmap_size = cur_bitmap_size;

        /* Initialize global_min_hit_count */
        global_min_hit_count = cur_hit_count;

        // initialize virgin_bits
        while (i--) {

            if (unlikely(*current)) discover_word(&ret, current, virgin);

            current++;
            virgin++;

        }

        if (unlikely(ret) && likely(virgin_map == afl->virgin_bits))
            afl->bitmap_changed = 1;

        original_virgin_bits = afl->virgin_bits;  // initialize original_virgin_bits

        u32 len = (afl->fsrv.map_size >> 3);
        trace_mini_ori = ck_alloc(len);
        minimize_bits(afl, trace_mini_ori, afl->fsrv.trace_bits); // initialize trace_mini_ori

        return ret;
    } // initialize virgin_bits finished

    /* STEP 1: check bitmap size */
    u64 cur_bitmap_size;

    cur_bitmap_size = count_bytes(afl, afl->fsrv.trace_bits);
    if (likely(afl->total_min_bitmap_size)) {
        // compare current bitmap_size with the global minimum bitmap_size that we have ever seen
        if (cur_bitmap_size < afl->total_min_bitmap_size) {
            // update total_min_bitmap_size with smaller one
            afl->total_min_bitmap_size = cur_bitmap_size;

            bms_decrease = 1;   // bitmap_size decreased!
        } else {}
    }


    /* STEP 2: check whether there is edge that no longer be hit */
    while (i--) {

        if (unlikely(*virgin + 1 != 0x0) && unlikely(*virgin & *current)) {
            // (*virgin + 1 != 0x0) means there is at least one path is hit in original bitmap
            // non-zero (*virgin & *current)
            // means the hit count between virgin and current is different


            u8* cur = (u8*)current;
            u8* vir = (u8*)virgin;

#ifdef WORD_SIZE_64

                if ((vir[0] != 0xff && cur[0] == 0x0) || (vir[1] != 0xff && cur[1] == 0x0) ||
                    (vir[2] != 0xff && cur[2] == 0x0) || (vir[3] != 0xff && cur[3] == 0x0) ||
                    (vir[4] != 0xff && cur[4] == 0x0) || (vir[5] != 0xff && cur[5] == 0x0) ||
                    (vir[6] != 0xff && cur[6] == 0x0) || (vir[7] != 0xff && cur[7] == 0x0)) {
                    // if there is a touched byte being untouched now
                    // it will mean there is a path disappeared
                    // update virgin_bits here!
                    if (vir[0] != 0xff && cur[0] == 0x0) {*((u8*)(virgin)+0) = 0xff;}
                    if (vir[1] != 0xff && cur[1] == 0x0) {*((u8*)(virgin)+1) = 0xff;}
                    if (vir[2] != 0xff && cur[2] == 0x0) {*((u8*)(virgin)+2) = 0xff;}
                    if (vir[3] != 0xff && cur[3] == 0x0) {*((u8*)(virgin)+3) = 0xff;}
                    if (vir[4] != 0xff && cur[4] == 0x0) {*((u8*)(virgin)+4) = 0xff;}
                    if (vir[5] != 0xff && cur[5] == 0x0) {*((u8*)(virgin)+5) = 0xff;}
                    if (vir[6] != 0xff && cur[6] == 0x0) {*((u8*)(virgin)+6) = 0xff;}
                    if (vir[7] != 0xff && cur[7] == 0x0) {*((u8*)(virgin)+7) = 0xff;}

                    cov_decrease = 1;    // coverage decreased!
                }
                if(unlikely(cur_hit_count < global_min_hit_count)) {
                // we only want to save the seed whose cur_hit_count is smaller than global min
                /* if we arrive this branch, means same bitmap_size, no global necessary edge was removed
                 * we have 2 kind of situations in this branch
                 * One: different hit count for at least one edge
                 * two: new edge was hit compared with virgin
                 *
                 * we won't update virgin
                 */
                global_min_hit_count = cur_hit_count;
                hcn_decrease = 1; // hit count sum decrease
            } else {}

#else
            if ((vir[0] != 0xff && cur[0] == 0x0) || (vir[1] != 0xff && cur[1] == 0x0) ||
                (vir[2] != 0xff && cur[2] == 0x0) || (vir[3] != 0xff && cur[3] == 0x0)) {
                // if there is a touched byte being untouched now
                // it will mean there is a path disappeared
                // update virgin_bits here!
                if (vir[0] != 0xff && cur[0] == 0x0) {*((u8*)(virgin)+0) = 0xff;}
                if (vir[1] != 0xff && cur[1] == 0x0) {*((u8*)(virgin)+1) = 0xff;}
                if (vir[2] != 0xff && cur[2] == 0x0) {*((u8*)(virgin)+2) = 0xff;}
                if (vir[3] != 0xff && cur[3] == 0x0) {*((u8*)(virgin)+3) = 0xff;}

                cov_decrease = 1;    // coverage decreased!

            }
            /* STEP 3: check total hit counts */
            if(unlikely(cur_hit_count < global_min_hit_count)) {
                /* if we arrive this branch, means same bitmap_size, no global necessary edge was removed
                 * we have 2 kind of situations in this branch
                 * One: different hit count for at least one edge
                 * two: new edge was hit compared with virgin
                 *
                 * we won't update virgin
                 */
                global_min_hit_count = cur_hit_count;
                hcn_decrease = 1; // hit count sum decrease
            } else {}

#endif /* ^WORD_SIZE_64 */

        }

        current++;
        virgin++;

    }

    if (cov_decrease) afl->bitmap_changed = 1;

    // bms cov hcn         ret
    // 1   1   1    ---->   7
    // 1   1   0    ---->   6
    // 1   0   1    ---->   5
    // 1   0   0    ---->   4
    // 0   1   1    ---->   3
    // 0   1   0    ---->   2
    // 0   0   1    ---->   1

    ret = bms_decrease * 4 + cov_decrease * 2 + hcn_decrease * 1;

    return ret;

}


/* Compact trace bytes into a smaller bitmap. We effectively just drop the
   count information here. This is called only sporadically, for some
   new paths. */

void minimize_bits(afl_state_t *afl, u8 *dst, u8 *src) {

  u32 i = 0;

  while (i < afl->fsrv.map_size) {

    if (*(src++)) { dst[i >> 3] |= 1 << (i & 7); }
    ++i;

  }

}

#ifndef SIMPLE_FILES

/* Construct a file name for a new test case, capturing the operation
   that led to its discovery. Returns a ptr to afl->describe_op_buf_256. */

u8 *describe_op(afl_state_t *afl, u8 new_bits, size_t max_description_len) {

  size_t real_max_len =
      MIN(max_description_len, sizeof(afl->describe_op_buf_256));
  u8 *ret = afl->describe_op_buf_256;

  if (unlikely(afl->syncing_party)) {

    sprintf(ret, "sync:%s,src:%06u", afl->syncing_party, afl->syncing_case);

  } else {

    sprintf(ret, "src:%06u", afl->current_entry);

    if (afl->splicing_with >= 0) {

      sprintf(ret + strlen(ret), "+%06d", afl->splicing_with);

    }

    sprintf(ret + strlen(ret), ",time:%llu", get_cur_time() - afl->start_time);

    if (afl->current_custom_fuzz &&
        afl->current_custom_fuzz->afl_custom_describe) {

      /* We are currently in a custom mutator that supports afl_custom_describe,
       * use it! */

      size_t len_current = strlen(ret);
      ret[len_current++] = ',';
      ret[len_current] = '\0';

      ssize_t size_left = real_max_len - len_current - strlen(",+cov") - 2;
      if (unlikely(size_left <= 0)) FATAL("filename got too long");

      const char *custom_description =
          afl->current_custom_fuzz->afl_custom_describe(
              afl->current_custom_fuzz->data, size_left);
      if (!custom_description || !custom_description[0]) {

        DEBUGF("Error getting a description from afl_custom_describe");
        /* Take the stage name as description fallback */
        sprintf(ret + len_current, "op:%s", afl->stage_short);

      } else {

        /* We got a proper custom description, use it */
        strncat(ret + len_current, custom_description, size_left);

      }

    } else {

      /* Normal testcase descriptions start here */
      sprintf(ret + strlen(ret), ",op:%s", afl->stage_short);

      if (afl->stage_cur_byte >= 0) {

        sprintf(ret + strlen(ret), ",pos:%d", afl->stage_cur_byte);

        if (afl->stage_val_type != STAGE_VAL_NONE) {

          sprintf(ret + strlen(ret), ",val:%s%+d",
                  (afl->stage_val_type == STAGE_VAL_BE) ? "be:" : "",
                  afl->stage_cur_val);

        }

      } else {

        sprintf(ret + strlen(ret), ",rep:%d", afl->stage_cur_val);

      }

    }

  }

    // bms cov hcn         ret
    // 1   1   1    ---->   7
    // 1   1   0    ---->   6
    // 1   0   1    ---->   5
    // 1   0   0    ---->   4
    // 0   1   1    ---->   3
    // 0   1   0    ---->   2
    // 0   0   1    ---->   1

  if (new_bits == 1) { strcat(ret, ",-hcn"); }
  else if (new_bits == 2) { strcat(ret, ",-cov"); }
  else if (new_bits == 3) { strcat(ret, ",-cov_hcn"); }
  else if (new_bits == 4) { strcat(ret, ",-bms"); }
  else if (new_bits == 5) { strcat(ret, ",-bms_hcn"); }
  else if (new_bits == 6) { strcat(ret, ",-bms_cov"); }
  else if (new_bits == 7) { strcat(ret, ",-bms_cov_hcn"); }
  else {}

    if (unlikely(strlen(ret) >= max_description_len))
    FATAL("describe string is too long");

  return ret;

}

#endif                                                     /* !SIMPLE_FILES */

/* Write a message accompanying the crash directory :-) */

static void write_crash_readme(afl_state_t *afl) {

  u8    fn[PATH_MAX];
  s32   fd;
  FILE *f;

  u8 val_buf[STRINGIFY_VAL_SIZE_MAX];

  sprintf(fn, "%s/crashes/README.txt", afl->out_dir);

  fd = open(fn, O_WRONLY | O_CREAT | O_EXCL, 0600);

  /* Do not die on errors here - that would be impolite. */

  if (unlikely(fd < 0)) { return; }

  f = fdopen(fd, "w");

  if (unlikely(!f)) {

    close(fd);
    return;

  }

  fprintf(
      f,
      "Command line used to find this crash:\n\n"

      "%s\n\n"

      "If you can't reproduce a bug outside of afl-fuzz, be sure to set the "
      "same\n"
      "memory limit. The limit used for this fuzzing session was %s.\n\n"

      "Need a tool to minimize test cases before investigating the crashes or "
      "sending\n"
      "them to a vendor? Check out the afl-tmin that comes with the fuzzer!\n\n"

      "Found any cool bugs in open-source tools using afl-fuzz? If yes, please "
      "drop\n"
      "an mail at <afl-users@googlegroups.com> once the issues are fixed\n\n"

      "  https://github.com/AFLplusplus/AFLplusplus\n\n",

      afl->orig_cmdline,
      stringify_mem_size(val_buf, sizeof(val_buf),
                         afl->fsrv.mem_limit << 20));      /* ignore errors */

  fclose(f);

}

/* Check if the result of an execve() during routine fuzzing is interesting,
   save or queue the input test case for further analysis if so. Returns 1 if
   entry is saved, 0 otherwise. */

u8 __attribute__((hot))
save_if_interesting(afl_state_t *afl, void *mem, u32 len, u8 fault) {

  if (unlikely(len == 0)) { return 0; }

  u8 *queue_fn = "";
  u8  few_bits = '\0';
  s32 fd;
  u8  keeping = 0, res, classified = 0;
  u64 cksum = 0;

  u8 fn[PATH_MAX];

  /* Update path frequency. */

  /* Generating a hash on every input is super expensive. Bad idea and should
     only be used for special schedules */
  if (unlikely(afl->schedule >= FAST && afl->schedule <= RARE)) {

    cksum = hash64(afl->fsrv.trace_bits, afl->fsrv.map_size, HASH_CONST);

    /* Saturated increment */
    if (afl->n_fuzz[cksum % N_FUZZ_SIZE] < 0xFFFFFFFF)
      afl->n_fuzz[cksum % N_FUZZ_SIZE]++;

  }

  if (likely(fault == afl->crash_mode)) {

    /* Keep if there are few bits in the map. 
    Keep if hit count is less than min hit count too.
    If hit count is more than min, keep it at a probability depending on the distance to min.
    Add to queue for future fuzzing, etc. */
    classify_counts(&afl->fsrv);
    few_bits = has_few_bits(afl, afl->virgin_bits);

    if (likely(!few_bits)) {

      return 0; // there are no few bits

    }
    else if(likely(few_bits == 1)){
      if(unlikely(cur_hit_count < global_min_hit_count)){}
      else {
        if(cur_hit_count-global_min_hit_count > R(global_min_hit_count / 2)) return 0;
        /* 0.5*min is the upper limit of cur - min. 
        If cur - min<0.5*min, A linear probability decides whether we keep the case or not.
        0.5 needs to be adjust. */
      }
    }

    classified = few_bits;

#ifndef SIMPLE_FILES

    queue_fn = alloc_printf(
        "%s/queue/id:%06u,%s", afl->out_dir, afl->queued_paths,
        describe_op(afl, few_bits, NAME_MAX - strlen("id:000000,")));

#else

    queue_fn =
        alloc_printf("%s/queue/id_%06u", afl->out_dir, afl->queued_paths);

#endif                                                    /* ^!SIMPLE_FILES */
    fd = open(queue_fn, O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (unlikely(fd < 0)) { PFATAL("Unable to create '%s'", queue_fn); }
    ck_write(fd, mem, len, queue_fn);
    close(fd);
    add_to_queue(afl, queue_fn, len, 0);

#ifdef INTROSPECTION
    if (afl->custom_mutators_count && afl->current_custom_fuzz) {

      LIST_FOREACH(&afl->custom_mutator_list, struct custom_mutator, {

        if (afl->current_custom_fuzz == el && el->afl_custom_introspection) {

          const char *ptr = el->afl_custom_introspection(el->data);

          if (ptr != NULL && *ptr != 0) {

            fprintf(afl->introspection_file, "QUEUE CUSTOM %s = %s\n", ptr,
                    afl->queue_top->fname);

          }

        }

      });

    } else if (afl->mutation[0] != 0) {

      fprintf(afl->introspection_file, "QUEUE %s = %s\n", afl->mutation,
              afl->queue_top->fname);

    }

#endif

    if (few_bits == 2) {

      afl->queue_top->has_new_cov = 1;
      ++afl->queued_with_cov;

    }

    if (cksum)
      afl->queue_top->exec_cksum = cksum;
    else
      cksum = afl->queue_top->exec_cksum =
          hash64(afl->fsrv.trace_bits, afl->fsrv.map_size, HASH_CONST);

    if (afl->schedule >= FAST && afl->schedule <= RARE) {

      afl->queue_top->n_fuzz_entry = cksum % N_FUZZ_SIZE;
      afl->n_fuzz[afl->queue_top->n_fuzz_entry] = 1;

    }

    /* Try to calibrate inline; this also calls update_bitmap_score() when
       successful. */

    res = calibrate_case(afl, afl->queue_top, mem, afl->queue_cycle - 1, 0);

    if (unlikely(res == FSRV_RUN_ERROR)) {

      FATAL("Unable to execute target application");

    }

    if (likely(afl->q_testcase_max_cache_size)) {

      queue_testcase_store_mem(afl, afl->queue_top, mem);

    }

    keeping = 1;

  }

  switch (fault) {

    case FSRV_RUN_TMOUT:

      /* Timeouts are not very interesting, but we're still obliged to keep
         a handful of samples. We use the presence of new bits in the
         hang-specific bitmap as a signal of uniqueness. In "non-instrumented"
         mode, we just keep everything. */

      ++afl->total_tmouts;

      if (afl->unique_hangs >= KEEP_UNIQUE_HANG) { return keeping; }

      if (likely(!afl->non_instrumented_mode)) {

        if (!classified) {

          classify_counts(&afl->fsrv);
          classified = 1;

        }

        simplify_trace(afl, afl->fsrv.trace_bits);

        if (!has_few_bits(afl, afl->virgin_tmout)) { return keeping; }

      }

      ++afl->unique_tmouts;
#ifdef INTROSPECTION
      if (afl->custom_mutators_count && afl->current_custom_fuzz) {

        LIST_FOREACH(&afl->custom_mutator_list, struct custom_mutator, {

          if (afl->current_custom_fuzz == el && el->afl_custom_introspection) {

            const char *ptr = el->afl_custom_introspection(el->data);

            if (ptr != NULL && *ptr != 0) {

              fprintf(afl->introspection_file,
                      "UNIQUE_TIMEOUT CUSTOM %s = %s\n", ptr,
                      afl->queue_top->fname);

            }

          }

        });

      } else if (afl->mutation[0] != 0) {

        fprintf(afl->introspection_file, "UNIQUE_TIMEOUT %s\n", afl->mutation);

      }

#endif

      /* Before saving, we make sure that it's a genuine hang by re-running
         the target with a more generous timeout (unless the default timeout
         is already generous). */

      if (afl->fsrv.exec_tmout < afl->hang_tmout) {

        u8 new_fault;
        write_to_testcase(afl, mem, len);
        new_fault = fuzz_run_target(afl, &afl->fsrv, afl->hang_tmout);
        classify_counts(&afl->fsrv);

        /* A corner case that one user reported bumping into: increasing the
           timeout actually uncovers a crash. Make sure we don't discard it if
           so. */

        if (!afl->stop_soon && new_fault == FSRV_RUN_CRASH) {

          goto keep_as_crash;

        }

        if (afl->stop_soon || new_fault != FSRV_RUN_TMOUT) { return keeping; }

      }

#ifndef SIMPLE_FILES

      snprintf(fn, PATH_MAX, "%s/hangs/id:%06llu,%s", afl->out_dir,
               afl->unique_hangs,
               describe_op(afl, 0, NAME_MAX - strlen("id:000000,")));

#else

      snprintf(fn, PATH_MAX, "%s/hangs/id_%06llu", afl->out_dir,
               afl->unique_hangs);

#endif                                                    /* ^!SIMPLE_FILES */

      ++afl->unique_hangs;

      afl->last_hang_time = get_cur_time();

      break;

    case FSRV_RUN_CRASH:

    keep_as_crash:

      /* This is handled in a manner roughly similar to timeouts,
         except for slightly different limits and no need to re-run test
         cases. */

      ++afl->total_crashes;

      if (afl->unique_crashes >= KEEP_UNIQUE_CRASH) { return keeping; }

      if (likely(!afl->non_instrumented_mode)) {

        if (!classified) {

          classify_counts(&afl->fsrv);

        }

        simplify_trace(afl, afl->fsrv.trace_bits);

        if (!has_few_bits(afl, afl->virgin_crash)) { return keeping; }

      }

      if (unlikely(!afl->unique_crashes)) { write_crash_readme(afl); }

#ifndef SIMPLE_FILES

      snprintf(fn, PATH_MAX, "%s/crashes/id:%06llu,sig:%02u,%s", afl->out_dir,
               afl->unique_crashes, afl->fsrv.last_kill_signal,
               describe_op(afl, 0, NAME_MAX - strlen("id:000000,sig:00,")));

#else

      snprintf(fn, PATH_MAX, "%s/crashes/id_%06llu_%02u", afl->out_dir,
               afl->unique_crashes, afl->last_kill_signal);

#endif                                                    /* ^!SIMPLE_FILES */

      ++afl->unique_crashes;
#ifdef INTROSPECTION
      if (afl->custom_mutators_count && afl->current_custom_fuzz) {

        LIST_FOREACH(&afl->custom_mutator_list, struct custom_mutator, {

          if (afl->current_custom_fuzz == el && el->afl_custom_introspection) {

            const char *ptr = el->afl_custom_introspection(el->data);

            if (ptr != NULL && *ptr != 0) {

              fprintf(afl->introspection_file, "UNIQUE_CRASH CUSTOM %s = %s\n",
                      ptr, afl->queue_top->fname);

            }

          }

        });

      } else if (afl->mutation[0] != 0) {

        fprintf(afl->introspection_file, "UNIQUE_CRASH %s\n", afl->mutation);

      }

#endif
      if (unlikely(afl->infoexec)) {

        // if the user wants to be informed on new crashes - do that
#if !TARGET_OS_IPHONE
        // we dont care if system errors, but we dont want a
        // compiler warning either
        // See
        // https://stackoverflow.com/questions/11888594/ignoring-return-values-in-c
        (void)(system(afl->infoexec) + 1);
#else
        WARNF("command execution unsupported");
#endif

      }

      afl->last_crash_time = get_cur_time();
      afl->last_crash_execs = afl->fsrv.total_execs;

      break;

    case FSRV_RUN_ERROR:
      FATAL("Unable to execute target application");

    default:
      return keeping;

  }

  /* If we're here, we apparently want to save the crash or hang
     test case, too. */

  fd = open(fn, O_WRONLY | O_CREAT | O_EXCL, 0600);
  if (unlikely(fd < 0)) { PFATAL("Unable to create '%s'", fn); }
  ck_write(fd, mem, len, fn);
  close(fd);

  return keeping;

}

