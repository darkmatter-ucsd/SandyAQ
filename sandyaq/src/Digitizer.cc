#include "Digitizer.hh"

Digitizer::Digitizer(std::string& sConfigFile, CommonConfig_t &CommonConfig, const char* BoardTypeName, int BoardIndex) : m_BoardType(BoardTypeName){
    inih::INIReader r{ sConfigFile };
    int ret = 0;

    m_iBoardIndex = BoardIndex;
    int i = m_iBoardIndex;

    m_CommonConfig = CommonConfig;

    std::cout << i << "\n";
    std::string sBoardCategory = "BOARD-"+std::to_string(i);


    m_iNChannels = r.Get<uint32_t>(sBoardCategory, "N_CHANNELS");
    m_iPostTrigger = r.Get<uint32_t>(sBoardCategory, "POST_TRIGGER");
    m_sFirmware = r.Get<std::string>(sBoardCategory, "FIRMWARE");
    m_sLinkType = r.Get<std::string>(sBoardCategory, "OPEN");

    std::vector<std::string> sLinkValues = r.GetVector<std::string>(sBoardCategory, "OPEN_VALUES");
    for (const std::string &s : sLinkValues) {
        m_iLinkValues.push_back(std::stoi(s, nullptr, 16));
    }

    m_iOpenChannels = r.GetVector<uint32_t>(sBoardCategory, "CHANNEL_LIST");
    // m_iCoincidences[i] = r.Get<uint32_t>(sBoardCategory, "COINCIDENCE");
    // m_iPulsePolarity[i] = r.Get<uint32_t>(sBoardCategory, "PULSE_POLARITY");
    m_iETTT = r.Get<uint32_t>(sBoardCategory, "EXTENDED_TTT");
    std::string ExtTrgMode = r.Get<std::string>(sBoardCategory, "EXTERNAL_TRIGGER");
    m_iExternalTriggerEnabled = TriggerModeMap[ExtTrgMode];
    m_sFPIOLevel = r.Get<std::string>(sBoardCategory, "FPIO_LEVEL");

    //Plot settings
    int m_iPlottingEnabled = r.Get<int>(sBoardCategory, "PLOTTING");
    if (m_iPlottingEnabled) {
            m_iPlottedChannels = (r.GetVector<int>(sBoardCategory, "PLOT_CHANNELS"));
            //Set TGraphs
            for (int c=0; c<m_iPlottedChannels.size(); c++){
                TGraph* ch_graph = new TGraph();
                m_Graphs.push_back(ch_graph);
            }
    }

    m_iEnableMask = 0;

    //NOTE: For x742 models, these refer to the channel GROUPS.But m_iNChannels is still a multiple of 8
    std::vector<uint32_t> iPulsePolarity;
    for (const uint32_t ch : m_iOpenChannels) {
        std::string sBoardChannel = sBoardCategory+"_CHANNEL-"+std::to_string(ch);
        m_iEnableMask += 1 << ch;
        int iDCValue;
        try{
            iDCValue = r.Get<int>(sBoardChannel, "DC_OFFSET");
        } catch (const std::runtime_error& e) {
            std::cerr << "WARNING: DC_OFFSET is not applied to board " << i << " channel "<< ch<<", maybe this model doesn't have this option.\n";
            iDCValue = 0;
        }

        iDCValue = (int)((iDCValue + 50) * 65535 / 100);
        m_iChannelDCOffset.push_back(iDCValue);

        uint32_t iTrigThresh;
        try{
            iTrigThresh = r.Get<uint32_t>(sBoardChannel, "TRIGGER_THRESHOLD");
        } catch (const std::runtime_error& e) {
            std::cerr << "WARNING: TRIGGER_THRESHOLD is not applied to board " << i << " channel "<< ch<<", maybe this model doesn't have this option.\n";
            iTrigThresh = 0;
        }
        m_iTriggerThresholds.push_back(iTrigThresh);

        std::string sTrigSet;
        try{
            sTrigSet = r.Get<std::string>(sBoardChannel, "CHANNEL_TRIGGER");
        } catch(const std::runtime_error& e) {
            std::cerr << "WARNING: CHANNEL_TRIGGER is not applied to board " << i << " channel "<< ch<<", maybe this model doesn't have this option.\n";
            sTrigSet = "DISABLED";
        }
        
        // sTriggerSettings.push_back(TriggerModeMap[sTrigSet]);
        m_sChannelTriggerSetting[ch] = TriggerModeMap[sTrigSet];

        m_iPulsePolarity.push_back(r.Get<uint32_t>(sBoardChannel, "PULSE_POLARITY"));
    }

    ret = OpenDigitizer();
}

Digitizer::~Digitizer() {
    // Delete TGraphs
    if (m_iPlottingEnabled){
        for (int c=0; c<m_iPlottedChannels.size(); c++){
            delete m_Graphs[c];
        }
    }
};

int Digitizer::OpenDigitizer() {
    int ret = 0;

    CAEN_DGTZ_ConnectionType iLinkType;
    int iLinkNum;
    int iConetNode;
    uint32_t iBaseAddress;

    if (m_sLinkType == "USB") {
        iLinkType = CAEN_DGTZ_USB;
    }
    else if (m_sLinkType == "PCI") {
        iLinkType = CAEN_DGTZ_OpticalLink;
    }
    else if (m_sLinkType == "USB_A4818") {
        iLinkType = CAEN_DGTZ_USB_A4818;
    }
    else if (m_sLinkType == "USB_A4818_V2718") {
        iLinkType = CAEN_DGTZ_USB_A4818_V2718;
    }
    else if (m_sLinkType == "USB_A4818_V3718") {
        iLinkType = CAEN_DGTZ_USB_A4818_V3718;
    }
    else if (m_sLinkType == "USB_A4818_V4718") {
        iLinkType = CAEN_DGTZ_USB_A4818_V4718;
    }
    else if (m_sLinkType == "USB_V4718") {
        iLinkType = CAEN_DGTZ_USB_V4718;
    }
    else{
        std::cout << "ERROR: Invalid link type" <<std::endl;
        exit(EXIT_FAILURE);
    }
    
    //Open the digitizer
    ret = CAEN_DGTZ_OpenDigitizer(iLinkType, m_iLinkValues[0], m_iLinkValues[1], m_iLinkValues[2], &m_iHandle);
    
    if (ret) {
        std::cout << "ERROR: Can't open digitizer " << std::endl;
        Quit();
    }

    //Get the board info
    CAEN_DGTZ_BoardInfo_t BoardInfo;
    ret = CAEN_DGTZ_GetInfo(m_iHandle, &BoardInfo);
    m_BoardInfo = BoardInfo;
    if (ret) {
        std::cout << "ERROR: Can't get the board info for digitizer " << std::endl;
        Quit();
    }

    //See if the PLL has been unlocked
    ret = CheckBoardFailureStatus(m_iHandle, BoardInfo);
    if (ret) {
        std::cout << "ERROR: PLL has been unlocked" << std::endl;
        Quit();
    }

    m_bOpen = true;

    return ret;
}

int Digitizer::ProgramDigitizer() {}
void Digitizer::Quit() {}
int Digitizer::SetLVDSSync(int isMaster, int iDaisyChainNum, int iTotalNBoards) {}