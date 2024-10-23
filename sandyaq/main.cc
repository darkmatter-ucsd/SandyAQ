#include "Ini.hh"
#include "V1725.hh"
#include "V1742.hh"
#include "X742CorrectionRoutines.h"
// #include "Utils.hh"
#include "GlobalControl.hh"
#include "CommonConfig.hh"
#include <getopt.h>
#include <string>
#include <vector>
#include <iostream>
#include <fstream>
#include <cstring>
#include <cstdlib>
#include <queue>

int main(int argc, char* argv[]) {
    int c = 0;
    int ret = 0;
    bool bConfigFileExists = false;
    int iNEventsTotal = 100;
    std::string sConfigFile;
    std::string sOutputFile;

    while ((c = getopt(argc, argv, "c:n:f:")) != -1){
        switch (c){
            case 'c':
                bConfigFileExists = true;
                sConfigFile.assign(optarg);
                std::cout << "Configuration file: " << sConfigFile << '\n';
                break;
            case 'n':
                iNEventsTotal = atoi(optarg);
                break;
            case 'f':
                sOutputFile.assign(optarg);
                break;
            default:
                break;
        }
    }

	if (!bConfigFileExists) {
		std::cout << "ERROR: No config file" << std::endl;
		exit(EXIT_FAILURE);
	}

    inih::INIReader r{ sConfigFile };
    
    CommonConfig_t config;
    ParseCommonConfig(sConfigFile, config);

    std::map<std::string, int> boardTypeCount;
    std::vector<std::string> boardTypes;
    std::vector<Digitizer*> digitizers;
    int iNTotBoards = config.sBoardTypes.size();
    char *buffer[iNTotBoards] = {nullptr};

    // count digitizer types
    for (const auto& bt : config.sBoardTypes) {
        boardTypeCount[bt]++;
    }

    // Print the unique digitizer types and their counts
    for (const auto& pair : boardTypeCount) {
        boardTypes.push_back(pair.first);
        std::cout << "Board: " << pair.first << ", Count: " << pair.second << std::endl;
    }


    std::vector<CAEN_DGTZ_X742_EVENT_t*> Events742;
    for (const auto& pair : boardTypeCount){
        if (pair.first == "V1725") {
            V1725* dgtz = new V1725(sConfigFile, config);
            digitizers.push_back(dgtz);
        }
        else if (pair.first == "V1742") {
            V1742* dgtz = new V1742(sConfigFile, config);
            // std::cout<<dgtz->m_BoardType<<"\n";
            digitizers.push_back(dgtz);
            for (int i=0; i<dgtz->m_iNBoards; i++){
                Events742.push_back(NULL);
                ret = CAEN_DGTZ_AllocateEvent(dgtz->m_iHandles[i], (void**)&Events742[i]);
                if (ret!=CAEN_DGTZ_Success){
                    std::cout <<"ERROR: Failed to allocate event for V1742 number "<<i<<"\n";
                    return -1;
                }
            }

        }
        //TO DO: Add else if statements for V1720s
    }

    // MAX_X742_GROUP_SIZE is defined in CAENDigitizer
    CAEN_DGTZ_DRS4Correction_t X742Tables[MAX_X742_GROUP_SIZE];

    for (Digitizer* dgtz : digitizers) {
        ret = dgtz->ProgramDigitizers();
        if (ret != 0){
            std::cout << "ERROR in programming one of the digitizers"<<std::endl;
            exit(EXIT_FAILURE);
        }
        PrintVec1d(dgtz->m_sLinkTypes);
        PrintVec2d(dgtz->m_iLinkValues);
        std::cout << (dgtz->m_iEnableMask[0]) << " " << (dgtz->m_iEnableMask[1]) << "\n";
    }   
    std::cout << "Programmed the digitizers\n";

    if (iNTotBoards>1){
        ret = SetSyncMode(digitizers, &config);
        if (ret!=0) {
            std::cout <<"ERROR in setting the synchronization mode of the digitizers"<<std::endl;
            exit(EXIT_FAILURE);
        }
    }
    std::cout << digitizers.size();
    std::cout << "Set synchronization \n";

    //Allocate readout buffer
    int iTotBoardIndex = 0;
    uint32_t iAllocatedSize;
    for (Digitizer* dgtz : digitizers) {
        for (int i = 0; i < dgtz->m_iNBoards; i++){
            std::cout <<"Allocating the readout buffers\n";
            ret |= CAEN_DGTZ_MallocReadoutBuffer(dgtz->m_iHandles[i], &buffer[iTotBoardIndex], &iAllocatedSize); 
            if (ret) {
                printf("Can't allocate memory for the acquisition\n");
                exit(EXIT_FAILURE);
            }
            else {
                printf("Allocated memory for board %d\n", iTotBoardIndex);
            }
            iTotBoardIndex++;
        }
    }

    // ret
    // ForceClockSync(digitizers[0]->m_iHandles[0]); //Sync is on board 0 always!

    //set the output file
    FILE* event_file[iNTotBoards] = {NULL};
    FILE* event_file_test[iNTotBoards] = {NULL};
    for (int i = 0; i < iNTotBoards; i++){
        std::string eventFileName = sOutputFile + "board_" + std::to_string(i) + ".bin";
        std::string eventFileNameTest = "partest_" + sOutputFile + "board_" + std::to_string(i) + ".bin";
        event_file[i] = fopen(eventFileName.c_str(), "w");
        event_file_test[i] = fopen(eventFileNameTest.c_str(), "w");
    }
    
    uint32_t iNumEventsAcquired[iNTotBoards] = {0};
    bool bAcquisitionStarted = false;
    uint32_t iBufferSize, iNumEvents = 0;
    uint64_t CurrentTime;
    uint64_t PrevRateTime[iNTotBoards];
    uint64_t ElapsedTime[iNTotBoards];
    uint32_t Nb[iNTotBoards]={0}, Ne[iNTotBoards]={0};
    
    RunControlVars_t runcontrol;
    runcontrol.quit=0;
    runcontrol.start=0;
    runcontrol.acquiring=0;

    //Special allocations for the events if you want to decode them
    // CAEN_DGTZ_UINT16_EVENT_t *Event16=NULL
    char *EventPtr = NULL;
    CAEN_DGTZ_EventInfo_t EventInfo;
    
    std::cout<<"\nPress: [s] to start/stop acquiring, [q] to quit\n";
    std::vector<std::queue<char*>> DigitizerBufferQueue(iNTotBoards);
    std::vector<std::queue<uint32_t>> BufferSizeQueue(iNTotBoards);

    #pragma omp parallel shared(runcontrol, iBufferSize)
    {
        //Reader thread
        #pragma omp single nowait
        {
            while (!runcontrol.quit){
                CheckKeyboardCommands(&runcontrol);

                if ((!runcontrol.acquiring)&&(runcontrol.start)){
                    StartRun(digitizers, &config);
                    for (int i = 0; i < iNTotBoards; i++) {
                        PrevRateTime[i] = get_time();
                    }
                    runcontrol.acquiring=1;
                }
                
                if (runcontrol.acquiring){
                    iTotBoardIndex = 0;
                    for (Digitizer* dgtz : digitizers) {
                        for (int i = 0; i < dgtz->m_iNBoards; i++){
                            ret = CAEN_DGTZ_ReadData(dgtz->m_iHandles[i], CAEN_DGTZ_SLAVE_TERMINATED_READOUT_MBLT, buffer[iTotBoardIndex], &iBufferSize);
                            PrintError(iTotBoardIndex, "Reading Events", "buffer", ret);
                            // printf("Buffer Size: %d\n",iBufferSize);
                            if (iBufferSize != 0) {
                                ret = CAEN_DGTZ_GetNumEvents(dgtz->m_iHandles[i], buffer[iTotBoardIndex], iBufferSize, &iNumEvents);
                                PrintError(iTotBoardIndex, "Getting Number of Events", "buffer", ret);
                                
                                //Push buffer to queue
                                char* DataChunk = (char*) std::malloc(iBufferSize);
                                std::memcpy(DataChunk, buffer[iTotBoardIndex], iBufferSize);
                                DigitizerBufferQueue[iTotBoardIndex].push(DataChunk);
                                BufferSizeQueue[iTotBoardIndex].push(iBufferSize);

                                //The V1742 events need to be treated differently than the rest of the events
                                //due to their correction tables
                                // if (dgtz->m_BoardType=="V1742"){
                                //     for (int ev=0; ev<iNumEvents; ev++){
                                //         ret = CAEN_DGTZ_GetEventInfo(dgtz->m_iHandles[i], buffer[iTotBoardIndex], iBufferSize, ev, &EventInfo, &EventPtr);
                                //         ret = CAEN_DGTZ_DecodeEvent(dgtz->m_iHandles[i], EventPtr, (void**)&Events742[i]);
                                //         if (ret!=CAEN_DGTZ_Success){
                                //             std::cout<<"ERROR: Could not decode 742 event!\n";
                                //         }
                                //     }
                                // }

                                fwrite(buffer[iTotBoardIndex], 1, iBufferSize, event_file[iTotBoardIndex]);
                                Nb[iTotBoardIndex] += iBufferSize;
                                Ne[iTotBoardIndex] += iNumEvents;
                                iNumEventsAcquired[iTotBoardIndex] +=iNumEvents;
                            }


                            CurrentTime = get_time();
                            ElapsedTime[iTotBoardIndex] = CurrentTime - PrevRateTime[iTotBoardIndex];

                            if (ElapsedTime[iTotBoardIndex] > 1000) {
                                if (Nb[iTotBoardIndex] == 0)
                                    if (ret == CAEN_DGTZ_Timeout) printf ("Timeout...\n"); else printf("No data...\n");
                                else
                                    printf("Reading from board %d at %.2f MB/s (Trg Rate: %.2f Hz)\n", iTotBoardIndex, (float)Nb[iTotBoardIndex]/((float)ElapsedTime[iTotBoardIndex]*1048.576f), (float)Ne[iTotBoardIndex]*1000.0f/(float)ElapsedTime[iTotBoardIndex]);
                                    Nb[iTotBoardIndex] = 0;
                                    Ne[iTotBoardIndex] = 0;
                                    PrevRateTime[iTotBoardIndex] = CurrentTime;
                                    // std::cout <<"Acquisition status: "<<runcontrol.start<<"\n";
                                }

                            iTotBoardIndex++;
                        }
                    }
                }

                if (iNumEventsAcquired[0] >= iNEventsTotal){
                    runcontrol.start=0;
                    runcontrol.quit=1;
                    runcontrol.acquiring=0;
                }
                
                if (((!runcontrol.start)&&(runcontrol.acquiring))||((runcontrol.quit)&&(runcontrol.acquiring)))
                    StopRun(digitizers, &config);
            }
        }

        #pragma omp single nowait
        {
            bool bQueuesEmpty=false;
            while(!(runcontrol.quit && bQueuesEmpty)){
                int p_iTotBoardIndex = 0; //Board index for the processor
                int iTotalQueueSize = 0;
                for (Digitizer* dgtz : digitizers) {
                    for (int i = 0; i < dgtz->m_iNBoards; i++){
                        // if (dgtz->m_BoardType=="V1742"){
                        //     for (int ev=0; ev<iNumEvents; ev++){
                        //         ret = CAEN_DGTZ_GetEventInfo(dgtz->m_iHandles[i], buffer[iTotBoardIndex], iBufferSize, ev, &EventInfo, &EventPtr);
                        //         ret = CAEN_DGTZ_DecodeEvent(dgtz->m_iHandles[i], EventPtr, (void**)&Events742[i]);
                        //         if (ret!=CAEN_DGTZ_Success){
                        //             std::cout<<"ERROR: Could not decode 742 event!\n";
                        //         }
                        //     }
                        // }

                        //Check the queues
                        int queuelimit = (runcontrol.quit) ? 1 : 2; //If you've quit, there must be at least one element, otherwise, there must be two
                        iTotalQueueSize+=DigitizerBufferQueue[p_iTotBoardIndex].size();

                        if (DigitizerBufferQueue[p_iTotBoardIndex].size()>=queuelimit){
                            char* buf_from_q = DigitizerBufferQueue[p_iTotBoardIndex].front();
                            fwrite(buf_from_q, 1, BufferSizeQueue[p_iTotBoardIndex].front(), event_file_test[p_iTotBoardIndex]);
                            DigitizerBufferQueue[p_iTotBoardIndex].pop();
                            BufferSizeQueue[p_iTotBoardIndex].pop();
                            std::free(buf_from_q);
                        }

                        p_iTotBoardIndex++;
                    }
                }

                if (iTotalQueueSize==0)
                    bQueuesEmpty=true;
            }
        }
    }

    for (int i = 0; i < iNTotBoards; i++){
        fclose(event_file[i]);
        fclose(event_file_test[i]);
    }
    
    iTotBoardIndex = 0;
    for (Digitizer* dgtz : digitizers) {
        for (int i = 0; i < dgtz->m_iNBoards; i++){
            CAEN_DGTZ_SWStopAcquisition(dgtz->m_iHandles[i]);
            CAEN_DGTZ_FreeReadoutBuffer(&buffer[iTotBoardIndex]);
            if (dgtz->m_BoardType=="V1742")
                CAEN_DGTZ_FreeEvent(dgtz->m_iHandles[i], (void**)&Events742[i]);
            iTotBoardIndex++;
        }
    }

    for (Digitizer* dgtz : digitizers) {
        delete dgtz;
    }

    digitizers.clear();

    return 0;
}