/*
 * Written and maintained by Jiang Xiyue <xiyue_jiang@outlook.com>
 */

#include "pin.H"
#include <iostream>
#include <fstream>
#include <string.h>
#include <vector>

/* ===================================================================== */
/* Global Variables */
/* ===================================================================== */

std::ofstream TraceFile;
std::string gProgramName = "";
BOOL gStartRecord = FALSE;

/* ===================================================================== */
/* Commandline Switches */
/* ===================================================================== */

KNOB <string> KnobOutputFile(KNOB_MODE_WRITEONCE, "pintool", "o", "calltrace_addr.out", "specify trace file name");
KNOB <string> KnobBlockModule(KNOB_MODE_WRITEONCE, "pintool", "blockModule", "",
                                  "Modules not to be blocked, use ',' to seperate. Default: no blocked modules");
KNOB <string> KnobBlockFunction(KNOB_MODE_WRITEONCE, "pintool", "blockFunc", "",
                                "Functions not to be blocked, use ',' to seperate. Default: no blocked functions");
/* ===================================================================== */
/* Print Help Message                                                    */
/* ===================================================================== */

INT32 Usage() {
    cerr << "This tool produces a call trace." << endl << endl;
    cerr << KNOB_BASE::StringKnobSummary() << endl;
    return -1;
}

string invalid = "invalid_rtn";

std::string upper_string(const std::string &str) {
    string upper;
    std::transform(str.begin(), str.end(), std::back_inserter(upper), ::toupper);
    return upper;
}

/**
 * Split argument list by flag.
 * @param s String of arguments
 * @param sv Vector of strings
 * @param flag Separator of arguments, default ','
 */
void split(const string &s, vector <string> &sv, const char flag = ',') {
    sv.clear();
    istringstream iss(s);
    string temp;

    while (getline(iss, temp, flag)) {
        sv.push_back(temp);
    }

    return;
}

/**
 * Check whether an instrumented function is a blocked function.
 * @param address Unused
 * @param rtn Intel Pin RTN object
 * @return Is current RTN a blocked function.
 */
bool isBlockedFunction(ADDRINT address, RTN rtn) {
    if (KnobBlockFunction.Value().size() == 0)
        return false;

    vector <string> funcNames;
    split(KnobBlockFunction.Value(), funcNames, ',');

    if (!RTN_Valid(rtn))
        return false;

    if (!IMG_Valid(SEC_Img(RTN_Sec(rtn))))
        return false;

    string currentFuncName = RTN_Name(rtn);

    for (auto it : funcNames) {                 // we have functions to be blocked, let's iterate it!
        if (upper_string(currentFuncName).find(upper_string(it)) !=
            std::string::npos) {    // current function is one of our blocked functions
            return true;
        }
    }

    return false;
}

/**
 * Check whether an instrumented module is a blocked module.
 * @param address Unused
 * @param rtn Intel Pin RTN object
 * @return Is current RTN is inside a blocked module.
 */
bool IsBlockedModule(ADDRINT address, RTN rtn) {
    if (KnobBlockModule.Value().size() == 0) { return false; }

    if (!RTN_Valid(rtn))
        return false;

    if (!IMG_Valid(SEC_Img(RTN_Sec(rtn)))) { return false; }

    string imgName = IMG_Name(SEC_Img(RTN_Sec(rtn)));

    vector <string> blockedNames;
    split(KnobBlockModule.Value(), blockedNames, ',');
    for (auto it : blockedNames) {
        if (blockedNames.size() > 0 && upper_string(imgName).find(upper_string(it)) != std::string::npos)
            return true;
    }
    return false;
}

/**
 * Finding program name in Intel Pin command line arguments
 * @param argc
 * @param argv
 * @return Index of program name in command line arguments.
 */
int findProgramNameIndex(int argc, char **argv) {
    int programIndex = 0;
    std::string programName;

    std::string arguments;
    BOOL bMeetPin = FALSE;

    for (programIndex = 0; programIndex < argc; programIndex++) {
        string curArgument = argv[programIndex];
        transform(curArgument.begin(), curArgument.end(), curArgument.begin(), ::toupper);
        if (curArgument.find("PINBIN", curArgument.length() - 8) != string::npos) {
            bMeetPin = TRUE;
        }
        if (bMeetPin == TRUE && strcmp(argv[programIndex], "--") == 0) {
            programIndex = programIndex + 1;

            return programIndex;

        }
    }
    return -1;
}

/**
 * Check whether the control flow has entered the program under test.
 * This function modifies the global variable `gStartRecord`, which is the switch of our tracing mechanism.
 * @param address Unused
 * @param rtn Intel Pin RTN object
 */
void checkEntry(ADDRINT address, RTN rtn) {
    if (!RTN_Valid(rtn))
        return;

    if (!IMG_Valid(SEC_Img(RTN_Sec(rtn))))
        return;

    string imgName = IMG_Name(SEC_Img(RTN_Sec(rtn)));

    // Record traces from the user binary entry by default.
    if (gStartRecord == FALSE) {
        if (upper_string(imgName).find(upper_string(gProgramName.c_str())) != std::string::npos)
            gStartRecord = TRUE;
        else
            return;
    }
}

/* ===================================================================== */
// For debug use.
const string *Target2String(ADDRINT target) {
    IMG img = IMG_FindByAddress(target);
    string finalString = "";
    if (IMG_Valid(img)) {
        string name = IMG_Name(img);
        if (name == "") {
        } else {
            finalString = finalString + name;
        }
    }

    string name = RTN_FindNameByAddress(target);
    if (name == "") {
    } else {
        finalString = finalString + " " + name;
    }
    return new string(finalString);
}

/* ===================================================================== */
/**
 * Record a function caller's address.
 * @param caller_addr
 */
VOID do_call(ADDRINT caller_addr) {
    TraceFile << hexstr(caller_addr) << endl;
}

/* ===================================================================== */
/**
 * Record a function caller's address.
 * @param caller_addr
 */
VOID do_call_indirect(ADDRINT caller_addr) {
    do_call(caller_addr);
}

/* ===================================================================== */
VOID call_trace(TRACE trace, INS ins) {
    // Check whether the current trace has arrived at the user binary entry.
    // This call modifies the `gStartRecord` variable.
    checkEntry(INS_Address(ins), TRACE_Rtn(trace));

    if (gStartRecord == FALSE) {
        return;
    }

    // Skip __asan, __sanitizer etc. function calls.
    if (isBlockedFunction(INS_Address(ins), TRACE_Rtn(trace))) {
        return;
    }

    // Skip glibc tracing.
    if (IsBlockedModule(INS_Address(ins), TRACE_Rtn(trace))) {
        return;
    }

    if (INS_IsCall(ins)) {
        if (INS_IsDirectBranchOrCall(ins)) {
            INS_InsertPredicatedCall(ins, IPOINT_BEFORE, AFUNPTR(do_call), IARG_ADDRINT, INS_Address(ins),
                                     IARG_END);
        } else {
            INS_InsertCall(ins, IPOINT_BEFORE, AFUNPTR(do_call_indirect), IARG_ADDRINT, INS_Address(ins),
                           IARG_END);
        }
    }
}

VOID Trace(TRACE trace, VOID *v) {
    for (BBL bbl = TRACE_BblHead(trace); BBL_Valid(bbl); bbl = BBL_Next(bbl)) {
        INS tail = BBL_InsTail(bbl);
        call_trace(trace, tail);
    }
}

/* ===================================================================== */
VOID Fini(INT32 code, VOID *v) {
    TraceFile.close();
}

/* ===================================================================== */
/* Main                                                                  */
/* ===================================================================== */

int main(int argc, char *argv[]) {

    PIN_InitSymbols();

    if (PIN_Init(argc, argv)) {
        return Usage();
    }

    int programIndex = findProgramNameIndex(argc, argv);

    if (programIndex == -1) {
        programIndex = 0;
    }

    gProgramName = argv[programIndex];

    if (gProgramName.rfind("/") != string::npos) {
        gProgramName = gProgramName.substr(gProgramName.rfind("/") + 1);
    }

    TraceFile.open(KnobOutputFile.Value().c_str());

    TraceFile << hex;
    TraceFile.setf(ios::showbase);

    TRACE_AddInstrumentFunction(Trace, 0);
    PIN_AddFiniFunction(Fini, 0);

    // Never returns

    PIN_StartProgram();

    return 0;
}

/* ===================================================================== */
/* eof */
/* ===================================================================== */
