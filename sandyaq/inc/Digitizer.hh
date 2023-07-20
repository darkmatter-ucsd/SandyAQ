#ifndef DIGITIZER_HH
#define DIGITIZER_HH

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

class Digitizer {
    public:
        Digitizer(std::string& sConfigFile, CommonConfig_t &CommonConfig, const char* BoardTypeName);
        ~Digitizer();

        //Common for all
        int OpenDigitizers();
        
        //Needs to be set per digitizer
        virtual int ProgramDigitizers();
        virtual void Quit();

        //Map for Trigger Modes
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
        // std::vector<std::vector<CAEN_DGTZ_TriggerMode_t>> m_sChannelTriggerSetting;
        std::vector<std::map<uint32_t, CAEN_DGTZ_TriggerMode_t>> m_sChannelTriggerSetting;
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