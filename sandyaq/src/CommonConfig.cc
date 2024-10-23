#include "CommonConfig.hh"

int ParseCommonConfig(std::string& sConfigFile, CommonConfig_t& Config){
    inih::INIReader r{ sConfigFile };

    Config.iNBoards = r.Get<int>("COMMON", "N_BOARDS");
    for (int i = 0; i < Config.iNBoards; i++){
        Config.sBoardTypes = r.GetVector<std::string>("COMMON", "BOARD_TYPES");
    }
    Config.sGNUPlotPath = r.Get<std::string>("COMMON", "GNUPLOT_PATH");
    // Config.uiRecordLength = r.Get<uint32_t>("COMMON", "RECORD_LENGTH");
    Config.uiNumEventsBLT = r.Get<uint32_t>("COMMON", "MAX_NUM_EVENTS_BLT");

    Config.SyncMode = r.Get<std::string>("COMMON", "SYNC_MODE");
    Config.StartMode = r.Get<std::string>("COMMON", "START_MODE");

    return 0;
}