#ifndef COMMONCONFIG_HH
#define COMMONCONFIG_HH

#include "Ini.hh"
#include <vector>
#include <string>

#define MAX_BOARDS 8

typedef struct {
    int iNBoards;
    std::vector<std::string> sBoardTypes;
    std::string sGNUPlotPath;
    // std::string sCorrectionLevel;
    // std::string sOutputFileFormat;
    // std::string sOutputFileHeader;
    uint32_t uiRecordLength;
    uint32_t uiNumEventsBLT;

    std::string SyncMode;
    std::string StartMode;
} CommonConfig_t;

int ParseCommonConfig(std::string& sConfigFile, CommonConfig_t& Config);

#endif