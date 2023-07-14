#ifndef V1725_HH
#define V1725_HH

//cstdlib
#include <vector>
#include <string>
#include <stdio.h>
#include <math.h>
#include <float.h>

//CAEN
#include <CAENComm.h>
#include <CAENDigitizer.h>

//internal
#include "CommonConfig.hh"
#include "Utils.hh"

class V1725 {
    public:
        V1725(std::string& sConfigFile, CommonConfig_t &CommonConfig, int iBoardStart);
        ~V1725();

        int ParseConfigFile();
        int OpenDigitizers();
        int ProgramDigitizers();
        int ProgramDefault(int BoardNum);
        int ProgramDAW(int BoardNum);

        // int SetSyncMode(int *handle);
        // int StartRun(int *handle);
        // int StopRun(int *handle);

        void Quit();


        const uint32_t iNbits = 14;
        const double dTs = 4.0;

        //Map for Trigger Modes
        //TODO: add Veto mode
        std::map<std::string, CAEN_DGTZ_TriggerMode_t> TriggerModeMap = {
            {"DISABLED", CAEN_DGTZ_TRGMODE_DISABLED},
            {"ACQUISITION_ONLY", CAEN_DGTZ_TRGMODE_ACQ_ONLY},
            {"ACQUISITION_AND_TRGOUT", CAEN_DGTZ_TRGMODE_ACQ_AND_EXTOUT}
        };

        int m_iHandles[MAX_BOARDS];
        int m_bOpen[MAX_BOARDS];

    public:
        CommonConfig_t m_CommonConfig;
        int m_iNBoards = 0;

        //Board settings
        uint32_t m_iNChannels[MAX_BOARDS];
        uint32_t m_iPostTriggers[MAX_BOARDS];
        std::vector<std::string> m_sFirmwares;
        std::vector<std::string> m_sLinkTypes;
        std::vector<std::vector<uint32_t>> m_iLinkValues;
        std::vector<std::vector<uint32_t>> m_iOpenChannels;
        uint32_t m_iCoincidences[MAX_BOARDS];
        // uint32_t m_iPulsePolarity[MAX_BOARDS];
        uint32_t m_iETTT[MAX_BOARDS];
        std::vector<CAEN_DGTZ_TriggerMode_t> m_iExternalTriggerEnabled;
        // uint32_t m_iTriggerEdge[MAX_BOARDS];
        std::vector<std::string> m_sFPIOLevel;
        uint32_t m_iEnableMask[MAX_BOARDS];

        //Channel settings
        std::vector<std::vector<uint32_t>> m_iChannelDCOffset;
        std::vector<std::vector<uint32_t>> m_iTriggerThresholds;
        std::vector<std::vector<CAEN_DGTZ_TriggerMode_t>> m_sChannelTriggerSetting;
        std::vector<std::vector<uint32_t>> m_iPulsePolarity;

        //CAEN Returned info
        CAEN_DGTZ_BoardInfo_t m_BoardInfo[MAX_BOARDS];

        std::vector<std::string> m_sBoardColumnsWaveform = {"OPEN",
            "OPEN_VALUES",
            "CHANNEL_LIST",
            "COINCIDENCE",
            "PULSE_POLARITY",
            "EXTENDED_TTT",
            "EXTERNAL_TRIGGER",
            "TRIGGER_EDGE",
            "FPIO_LEVEL"};
        
        std::vector<std::string> m_sChannelColumnsWaveform = {"ENABLE_INPUT",
            "DC_OFFSET",
            "TRIGGER_THRESHOLD",
            "CHANNEL_TRIGGER"};
};

#endif