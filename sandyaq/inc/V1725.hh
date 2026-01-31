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

class V1725 : public Digitizer {
    public:
        V1725(std::string& sConfigFile, CommonConfig_t &CommonConfig, int BoardNum)
            : Digitizer(sConfigFile, CommonConfig, "V1725", BoardNum) {
                m_sConfigFile = sConfigFile;
                int iReadParamError = ReadX725SpecificParams();
                m_dDT = 4.0;
            };
        ~V1725();

        // int OpenDigitizers();
        int ReadX725SpecificParams();
        int ProgramDigitizer();
        int ProgramDefault();
        int ProgramDAW();

        int AllocateEvent();
        void FreeEvent();
        int PlotEvent(char *EventPtr, int channel, int plotChannelIndex);

        int SetLVDSSync(int isMaster, int iDaisyChainNum, int iTotalNBoards);

        void PlotEvent(char *EventPtr);
        // int SetSyncMode(int *handle);
        // int StartRun(int *handle);
        // int StopRun(int *handle);

        bool m_bIsFlashADC = true;

        void Quit();


        const uint32_t iNbits = 14;
        //Map for Trigger Modes
        //TODO: add Veto mode

        CAEN_DGTZ_UINT16_EVENT_t* m_PlottingEvent;
    
    private:
        std::string m_sConfigFile;
        uint32_t m_iRecordLength;
        uint32_t m_iCoincidences;

        
        //NOTE: There is only the plotting event because the V1725 is a good boy and doesn't need to be decoded so that correction tables can be applied.
        //The saving of the events can just be done via dumping the buffer
};

#endif