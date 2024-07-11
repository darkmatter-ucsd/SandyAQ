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
#include "Digitizer.hh"

class V1725 : public Digitizer{
    public:
        V1725(std::string& sConfigFile, CommonConfig_t &CommonConfig)
            : Digitizer(sConfigFile, CommonConfig, "V1725") {
                m_sConfigFile = sConfigFile;
                int iReadParamError = ReadX725SpecificParams();
            };
        ~V1725();

        // int OpenDigitizers();
        int ReadX725SpecificParams();
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
    
    private:
        std::string m_sConfigFile;
        std::vector<uint32_t> m_iRecordLength;
        uint32_t m_iCoincidences[MAX_BOARDS];
};

#endif