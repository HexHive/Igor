import argparse
import operator
import numpy as np
from scipy import stats

class TminStatics():
    def __init__(self, ori_poc_info=None, shrink_poc_info=None, output_path=None):
        """

        :param ori_res_file:
        :param shrink_res_file:
        :param output_path: dump the result into file
        """
        self._ori_poc_info_file = ori_poc_info
        self._shrink_poc_info_file = shrink_poc_info
        self._output_path = output_path
        self._ori_info = {}      # info parsed from ori_res_file
        self._shrink_info = {}   # info parsed from shrink_res_file
        self._tmin_shrink_res = {}   # tmin shrinking result statics

    @staticmethod
    def extractor(file):
        poc_name = -1
        poc_len = -1
        map_size = -1
        hit_cnt = -1

        result = {}

        with open(file, 'r') as f:
            content = f.readlines()
            for line in content:
                if "id:" in line:
                    poc_name = line.split("dry run with '")[1].split("'")[0]
                elif "len =" in line:
                    poc_len = int(line.split("len = ")[1].split(",")[0], 10)
                    map_size = int(line.split("map size = ")[1].split(",")[0], 10)
                    hit_cnt = int(line.split("hit counts = ")[1].split(",")[0], 10)
                else:
                    continue

                if (poc_name != -1) and (poc_len != -1) and (map_size != -1) and (hit_cnt != -1):
                    result[poc_name] = [poc_len, map_size, hit_cnt]

                    poc_name = -1
                    poc_len = -1
                    map_size = -1
                    hit_cnt = -1
                else:
                    continue

            return result

    def calculator(self):
        ori_res = TminStatics.extractor(self._ori_poc_info_file)
        shrink_res = TminStatics.extractor(self._shrink_poc_info_file)

        for poc_ori in ori_res.keys():
            for poc_shrink in shrink_res.keys():
                if poc_ori == poc_shrink:
                    len_ori = ori_res[poc_ori][0]
                    map_size_ori = ori_res[poc_ori][1]
                    hit_cnt_ori = ori_res[poc_ori][2]

                    len_shr = shrink_res[poc_shrink][0]
                    map_size_shr = shrink_res[poc_shrink][1]
                    hit_cnt_shr = shrink_res[poc_shrink][2]

                    rate_len = (len_ori - len_shr)/len_ori
                    rate_map = (map_size_ori - map_size_shr)/map_size_ori
                    rate_hit = (hit_cnt_ori - hit_cnt_shr)/hit_cnt_ori

                    self._tmin_shrink_res[poc_ori] = [rate_len, rate_map, rate_hit]
                else:
                    continue

    def res_static(self):
        rate_len_all = []
        rate_map_all = []
        rate_hit_all = []

        for key, value in self._tmin_shrink_res.items():
            rate_len = value[0]
            rate_map = value[1]
            rate_hit = value[2]

            rate_len_all.append(rate_len)
            rate_map_all.append(rate_map)
            rate_hit_all.append(rate_hit)

        # Median
        median_len = np.median(rate_len_all)
        median_map = np.median(rate_map_all)
        median_hit = np.median(rate_hit_all)

        # Mean
        mean_len = np.mean(rate_len_all)
        mean_map = np.mean(rate_map_all)
        mean_hit = np.mean(rate_hit_all)

        # Variance
        var_len = np.var(rate_len_all)
        var_map = np.var(rate_map_all)
        var_hit = np.var(rate_hit_all)

        # negative result
        neg_map = [i for i in rate_map_all if i < 0]
        neg_map_percent = len(neg_map)/len(rate_map_all)

        neg_hit = [j for j in rate_hit_all if j < 0]
        neg_map_percent = len(neg_hit)/len(rate_hit_all)

        # print now!
        print("======================MEDIAN==============================\n")
        print("len: {}%\n".format(median_len*100))
        print("map: {}%\n".format(median_map*100))
        print("hit: {}%\n".format(median_hit*100))
        print("=======================MEAN==============================\n")
        print("len: {}%\n".format(mean_len*100))
        print("map: {}%\n".format(mean_map*100))
        print("hit: {}%\n".format(mean_hit*100))
        print("======================VARIANCE===========================\n")
        print("len: {}%\n".format(var_len))
        print("map: {}%\n".format(var_map))
        print("hit: {}%\n".format(var_hit))
        print("======================NEGATIVE===========================\n")
        print("map: {}%\n".format(neg_map_percent*100))
        print("hit: {}%\n".format(neg_map_percent*100))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", help="original poc statics file")
    parser.add_argument("-t", help="tmin shrink poc statics file")
    parser.add_argument("-o", help="output path")

    args = parser.parse_args()

    P = TminStatics(args.i, args.t, args.o)
    P.calculator()
    P.res_static()

    print("Finished!\n")


if __name__ == "__main__":
    main()