#ifndef V1742_HH
#define V1742_HH

#define MAX_X742_NUM_BOARDS 8

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
#include "Digitizer.hh"

class V1742 : public Digitizer{
    public:
        V1742(std::string& sConfigFile, CommonConfig_t &CommonConfig)
            : Digitizer(sConfigFile, CommonConfig, "V1742") {
                m_sConfigFile = sConfigFile;
                int iReadParamError = ReadX742SpecificParams();
            };
        ~V1742();

        int ReadX742SpecificParams();
        int ProgramDigitizers();
        int ProgramDefault(int BoardNum);
        int SetLVDSSync(int BoardNum, int isMaster, int iDaisyChainNum, int iTotalNBoards);

        void Quit();

        const uint32_t iNbits = 12;
        double dTs;

    private:
        uint32_t m_iNch;
        std::string m_sConfigFile;
        std::vector<uint32_t> m_iFastTriggerDigitizing;
        std::vector<CAEN_DGTZ_TriggerMode_t> m_iFastTriggerEnabled;
        std::vector<CAEN_DGTZ_DRS4Frequency_t> m_iDRS4Frequency;
        std::vector<std::vector<uint32_t>> m_iGroupDCOffset;
        std::vector<std::vector<uint32_t>> m_iGroupTriggerThreshold;
        std::vector<uint32_t> m_iRecordLength;
        std::vector<int> m_iCorrections;
};

#endif