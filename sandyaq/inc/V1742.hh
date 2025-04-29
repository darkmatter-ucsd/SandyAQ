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
        V1742(std::string& sConfigFile, CommonConfig_t &CommonConfig, int BoardNum)
            : Digitizer(sConfigFile, CommonConfig, "V1742", BoardNum) {
                m_sConfigFile = sConfigFile;
                int iReadParamError = ReadX742SpecificParams();
            };
        ~V1742();

        int ReadX742SpecificParams();
        int ProgramDigitizer();
        int ProgramDefault();
        int SetLVDSSync(int isMaster, int iDaisyChainNum, int iTotalNBoards);

        void Quit();

        const uint32_t iNbits = 12;
        double x742DRS4dt[4] = {0.2, 0.5, 1., 1./0.75};

        bool m_bIsFlashADC = false;

    private:
        uint32_t m_iNch;
        std::string m_sConfigFile;
        uint32_t m_iFastTriggerDigitizing;
        CAEN_DGTZ_TriggerMode_t m_iFastTriggerEnabled;
        CAEN_DGTZ_DRS4Frequency_t m_iDRS4Frequency;
        uint32_t m_iGroupDCOffset[4];
        uint32_t m_iGroupTriggerThreshold[4];
        uint32_t m_iRecordLength;
        int m_iCorrections;
};

#endif