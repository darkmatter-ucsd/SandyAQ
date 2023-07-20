#include "Digitizer.hh"

Digitizer::Digitizer(std::string& sConfigFile, CommonConfig_t &CommonConfig, const char* BoardTypeName) {
    inih::INIReader r{ sConfigFile };
    int ret = 0;

    m_CommonConfig = CommonConfig;
    std::vector<int> boardIndices;

    for (int n=0; n < m_CommonConfig.sBoardTypes.size(); n++) {
        if (m_CommonConfig.sBoardTypes[n] == BoardTypeName){
            m_iNBoards++;
            boardIndices.push_back(n);
        }
    }

    // for (int i = iBoardStart; i < m_iNBoards+iBoardStart; i++){
    for (int i : boardIndices) {
        std::cout << i << "\n";
        std::string sBoardCategory = "BOARD-"+std::to_string(i);


        m_iNChannels[i] = r.Get<uint32_t>(sBoardCategory, "N_CHANNELS");
        m_iPostTriggers[i] = r.Get<uint32_t>(sBoardCategory, "POST_TRIGGER");
        m_sFirmwares.push_back(r.Get<std::string>(sBoardCategory, "FIRMWARE"));
        m_sLinkTypes.push_back(r.Get<std::string>(sBoardCategory, "OPEN"));

        std::vector<std::string> sLinkValues = r.GetVector<std::string>(sBoardCategory, "OPEN_VALUES");
        std::vector<uint32_t> iLinkValues;
        for (const std::string &s : sLinkValues) {
            iLinkValues.push_back(std::stoi(s, nullptr, 16));
        }
        // m_iLinkValues.push_back(r.GetVector<uint32_t>(sBoardCategory, "OPEN_VALUES"));
        m_iLinkValues.push_back(iLinkValues);
        m_iOpenChannels.push_back(r.GetVector<uint32_t>(sBoardCategory, "CHANNEL_LIST"));
        m_iCoincidences[i] = r.Get<uint32_t>(sBoardCategory, "COINCIDENCE");
        // m_iPulsePolarity[i] = r.Get<uint32_t>(sBoardCategory, "PULSE_POLARITY");
        m_iETTT[i] = r.Get<uint32_t>(sBoardCategory, "EXTENDED_TTT");
        std::string ExtTrgMode = r.Get<std::string>(sBoardCategory, "EXTERNAL_TRIGGER");
        m_iExternalTriggerEnabled.push_back(TriggerModeMap[ExtTrgMode]);
        m_sFPIOLevel.push_back(r.Get<std::string>(sBoardCategory, "FPIO_LEVEL"));

        m_iEnableMask[i] = 0;

        std::vector<uint32_t> iDCOffsets;
        std::vector<uint32_t> iTriggerThresholds;
        std::map<uint32_t,CAEN_DGTZ_TriggerMode_t> sTriggerSettings;
        std::vector<uint32_t> iPulsePolarity;
        for (const uint32_t ch : m_iOpenChannels[i]) {
            std::string sBoardChannel = sBoardCategory+"_CHANNEL-"+std::to_string(ch);
            m_iEnableMask[i] += 1 << ch;
            int iDCValue = r.Get<int>(sBoardChannel, "DC_OFFSET");
            iDCValue = (int)((iDCValue + 50) * 65535 / 100);
            iDCOffsets.push_back(iDCValue);

            uint32_t iTrigThresh = r.Get<uint32_t>(sBoardChannel, "TRIGGER_THRESHOLD");
            iTriggerThresholds.push_back(iTrigThresh);

            std::string sTrigSet = r.Get<std::string>(sBoardChannel, "CHANNEL_TRIGGER");
            // sTriggerSettings.push_back(TriggerModeMap[sTrigSet]);
            sTriggerSettings[ch] = TriggerModeMap[sTrigSet];

            iPulsePolarity.push_back(r.Get<uint32_t>(sBoardChannel, "PULSE_POLARITY"));
        }
        m_iChannelDCOffset.push_back(iDCOffsets);
        m_iTriggerThresholds.push_back(iTriggerThresholds);
        m_sChannelTriggerSetting.push_back(sTriggerSettings);
        m_iPulsePolarity.push_back(iPulsePolarity);
    }

    ret = OpenDigitizers();
}

Digitizer::~Digitizer() {};

int Digitizer::OpenDigitizers() {
    int ret = 0;

    for (int BoardNum = 0; BoardNum < m_iNBoards; BoardNum++) {
        int handle;

        CAEN_DGTZ_ConnectionType iLinkType;
        int iLinkNum;
        int iConetNode;
        uint32_t iBaseAddress;

        if (m_sLinkTypes[BoardNum] == "USB") {
            iLinkType = CAEN_DGTZ_USB;
        }
        else if (m_sLinkTypes[BoardNum] == "PCI") {
            iLinkType = CAEN_DGTZ_OpticalLink;
        }
        else if (m_sLinkTypes[BoardNum] == "USB_A4818") {
            iLinkType = CAEN_DGTZ_USB_A4818;
        }
        else if (m_sLinkTypes[BoardNum] == "USB_A4818_V2718") {
            iLinkType = CAEN_DGTZ_USB_A4818_V2718;
        }
        else if (m_sLinkTypes[BoardNum] == "USB_A4818_V3718") {
            iLinkType = CAEN_DGTZ_USB_A4818_V3718;
        }
        else if (m_sLinkTypes[BoardNum] == "USB_A4818_V4718") {
            iLinkType = CAEN_DGTZ_USB_A4818_V4718;
        }
        else if (m_sLinkTypes[BoardNum] == "USB_V4718") {
            iLinkType = CAEN_DGTZ_USB_V4718;
        }
        else{
            std::cout << "ERROR: Invalid link type" <<std::endl;
            exit(EXIT_FAILURE);
        }
        
        //Open the digitizer
        ret = CAEN_DGTZ_OpenDigitizer(iLinkType, m_iLinkValues[BoardNum][0], m_iLinkValues[BoardNum][1], m_iLinkValues[BoardNum][2], &handle);
        m_iHandles[BoardNum] = handle;
        if (ret) {
            std::cout << "ERROR: Can't open digitizer " << BoardNum << std::endl;
            Quit();
        }

        //Get the board info
        CAEN_DGTZ_BoardInfo_t BoardInfo;
        ret = CAEN_DGTZ_GetInfo(handle, &BoardInfo);
        m_BoardInfo[BoardNum] = BoardInfo;
        if (ret) {
            std::cout << "ERROR: Can't get the board info for digitizer " << BoardNum << std::endl;
            Quit();
        }

        //See if the PLL has been unlocked
        ret = CheckBoardFailureStatus(handle, BoardInfo);
        if (ret) {
            std::cout << "ERROR: PLL has been unlocked" << std::endl;
            Quit();
        }

        m_bOpen[BoardNum] = true;
    }

    return ret;
}

int Digitizer::ProgramDigitizers() {}
void Digitizer::Quit() {}