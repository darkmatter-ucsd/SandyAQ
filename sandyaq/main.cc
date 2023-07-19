#include "Ini.hh"
#include "V1725.hh"
// #include "Utils.hh"
#include "GlobalControl.hh"
#include "CommonConfig.hh"
#include <getopt.h>
#include <string>
#include <vector>
#include <iostream>
#include <fstream>

int main(int argc, char* argv[]) {
    int c = 0;
    int ret = 0;
    bool bConfigFileExists = false;
    std::string sConfigFile;

    while ((c = getopt(argc, argv, "c:")) != -1){
        switch (c){
            case 'c':
                bConfigFileExists = true;
                sConfigFile.assign(optarg);
                std::cout << "Configuration file: " << sConfigFile << '\n';
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

    for (const auto& pair : boardTypeCount){
        if (pair.first == "V1725") {
            V1725* dgtz = new V1725(sConfigFile, config);
            digitizers.push_back(dgtz);
            std::cout << dgtz->m_iHandles[0] << "\n";
            std::cout << dgtz->m_iHandles[1] << "\n";
        }
        //TO DO: Add else if statements for V1720s
    }

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
    

    ret = SetSyncMode(digitizers, &config);
    if (ret!=0) {
        std::cout <<"ERROR in setting the synchronization mode of the digitizers"<<std::endl;
        exit(EXIT_FAILURE);
    }
    
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
    FILE* event_file = NULL;
    event_file = fopen("event.bin", "w");
    uint32_t iNumEventsAcquired = 0;
    bool bAcquisitionStarted = false;
    uint32_t iBufferSize, iNumEvents = 0;
    uint64_t CurrentTime, PrevRateTime, ElapsedTime;
    uint32_t Nb[iNTotBoards]={0}, Ne[iNTotBoards]={0};
    
    // ret = CAEN_DGTZ_SWStartAcquisition(digitizers[0]->m_iHandles[0]);
    StartRun(digitizers, &config);

    // while(iNumEventsAcquired < 1000){
    //     ret = CAEN_DGTZ_ReadData(digitizers[0]->m_iHandles[0], CAEN_DGTZ_SLAVE_TERMINATED_READOUT_MBLT, buffer[0], &iBufferSize);
    //     printf("Buffer Size: %d\n",iBufferSize);
    //     if (iBufferSize != 0) {
    //         ret = CAEN_DGTZ_GetNumEvents(digitizers[0]->m_iHandles[0], buffer[0], iBufferSize, &iNumEvents);
    //         PrintError(iTotBoardIndex, "Getting Number of Events", "buffer", ret);
    //         fwrite(buffer[0], 1, iBufferSize, event_file);
    //     }
    //     iNumEventsAcquired+=iNumEvents;
    // }

    // ret = CAEN_DGTZ_SWStopAcquisition(digitizers[0]->m_iHandles[0]);
    // ret = CAEN_DGTZ_FreeReadoutBuffer(&buffer[0]);
    // /* close connection to boards */
    // ret = CAEN_DGTZ_CloseDigitizer(digitizers[0]->m_iHandles[0]);
    while(iNumEventsAcquired < 1000){
        iTotBoardIndex = 0;
        for (Digitizer* dgtz : digitizers) {
            for (int i = 0; i < dgtz->m_iNBoards; i++){
                ret = CAEN_DGTZ_ReadData(dgtz->m_iHandles[i], CAEN_DGTZ_SLAVE_TERMINATED_READOUT_MBLT, buffer[iTotBoardIndex], &iBufferSize);
                PrintError(iTotBoardIndex, "Reading Events", "buffer", ret);
                // printf("Buffer Size: %d\n",iBufferSize);
                if (iBufferSize != 0) {
                    std::cout << "Found some events!\n";
                    ret = CAEN_DGTZ_GetNumEvents(dgtz->m_iHandles[i], buffer[iTotBoardIndex], iBufferSize, &iNumEvents);
                    PrintError(iTotBoardIndex, "Getting Number of Events", "buffer", ret);
                    fwrite(buffer[iTotBoardIndex], 1, iBufferSize, event_file);
                }

                Nb[iTotBoardIndex] += iBufferSize;
                Ne[iTotBoardIndex] += iNumEvents;
                CurrentTime = get_time();
                ElapsedTime = CurrentTime - PrevRateTime;

                if (ElapsedTime > 1000) {
                    if (Nb[iTotBoardIndex] == 0)
                        if (ret == CAEN_DGTZ_Timeout) printf ("Timeout...\n"); else printf("No data...\n");
                    else
                        printf("Reading from board %d at %.2f MB/s (Trg Rate: %.2f Hz)\n", iTotBoardIndex, (float)Nb[iTotBoardIndex]/((float)ElapsedTime*1048.576f), (float)Ne[iTotBoardIndex]*1000.0f/(float)ElapsedTime);
                    if (iTotBoardIndex == iNTotBoards-1){
                        for (int b = 0; b < iNTotBoards; b++){
                            Nb[b] = 0;
                            Ne[b] = 0;
                        }
                        PrevRateTime = CurrentTime;
                    }
                }
                iTotBoardIndex++;
            }
        }
        // printf("Number of events acquired: %d\n", iNumEventsAcquired);
        // printf("Number of previsous events: %d\n", iNumEvents);

        iNumEventsAcquired+=iNumEvents;
    }
    printf("Have you gotten here?\n");
    StopRun(digitizers, &config);

    fclose(event_file);
    iTotBoardIndex = 0;
    for (Digitizer* dgtz : digitizers) {
        for (int i = 0; i < dgtz->m_iNBoards; i++){
            CAEN_DGTZ_SWStopAcquisition(dgtz->m_iHandles[i]);
            CAEN_DGTZ_FreeReadoutBuffer(&buffer[iTotBoardIndex]);
            iTotBoardIndex++;
        }
    }


    for (Digitizer* dgtz : digitizers) {
        delete dgtz;
    }

    digitizers.clear();

    // V1725 *digitizer = new V1725(sConfigFile, config);
    // PrintVec1d(digitizer->m_sLinkTypes);
    // PrintVec2d(digitizer->m_iLinkValues);
    // std::cout << (digitizer->m_iEnableMask[0]) << " " << (digitizer->m_iEnableMask[1]) << "\n";

    // digitizer->ProgramDigitizers();

    // printf(SetSyncMode(digitizer->m_iHandles));

    // delete digitizer;

    return 0;
}