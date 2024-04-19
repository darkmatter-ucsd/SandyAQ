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

// user input: -c configuration file -n number_of_events -d directory to save data -f file name

int main(int argc, char* argv[]) {
    int option = 0;
    int ret = 0;
    bool bConfigFileExists = false;
    int iNEvts = 0;
    std::string sConfigFile;
    std::string sDataDir;
    std::string sFileName;
    std::string sDataFullPath;

    while ((option = getopt(argc, argv, "c:n:d:f:")) != -1){
        switch (option){
            case 'c':
                bConfigFileExists = true;
                sConfigFile.assign(optarg);
                std::cout << "Configuration file: " << sConfigFile << '\n';
                break;
            case 'n':
                iNEvts = std::atoi(optarg);
                std::cout << "Number of events: " << iNEvts << '\n';
                break;
            case 'd':
                sDataDir.assign(optarg);
                break;
            case 'f':
                sFileName.assign(optarg);
                break;
            default:
                break;
        }
    }


	if (!bConfigFileExists) {
		std::cout << "ERROR: Missing config file, use -c to set it"  << std::endl;
		exit(EXIT_FAILURE);
	}
    if (iNEvts == 0) {
        std::cout << "ERROR: Missing number of events set, use -n to set it" << std::endl;
        exit(EXIT_FAILURE);
    }

    // Print the full path of the data file
    if(sDataDir.size() > 0 && sFileName.size() > 0){
        sDataFullPath = sDataDir + "/" + sFileName;
        std::cout << "Data file: " << sDataFullPath << std::endl;
    }


    inih::INIReader r{ sConfigFile };

    CommonConfig_t config;
    ParseCommonConfig(sConfigFile, config);


    std::map<std::string, int> boardTypeCount;
    std::vector<std::string> boardTypes;
    std::vector<Digitizer*> digitizers;
    int iNTotBoards = config.sBoardTypes.size(); // total number of boards
    char *buffer[iNTotBoards] = {nullptr}; // buffer for the readout

    // count digitizer types
    for (const auto& bt : config.sBoardTypes) {
        boardTypeCount[bt]++;
    }

    // Print the unique digitizer types and their counts
    // first: digitizer type, second: count
    for (const auto& pair : boardTypeCount) {
        boardTypes.push_back(pair.first);
        std::cout << "Board: " << pair.first << ", Count: " << pair.second << std::endl;
    }
    
    // Create digitizer objects
    for (const auto& pair : boardTypeCount){
        if (pair.first == "V1725") {
            V1725* dgtz = new V1725(sConfigFile, config);
            digitizers.push_back(dgtz);
            //std::cout << dgtz->m_iHandles[0] << "\n";
            //std::cout << dgtz->m_iHandles[1] << "\n";
        }
        //TO DO: Add else if statements for V1720s
    }

    // Program the digitizers (set the acquisition mode, record length, etc.)
    for (Digitizer* dgtz : digitizers) {
        ret = dgtz->ProgramDigitizers();
        if (ret != 0){
            std::cout << "  programming one of the digitizers"<<std::endl;
            exit(EXIT_FAILURE);
        }
        PrintVec1d(dgtz->m_sLinkTypes);
        PrintVec2d(dgtz->m_iLinkValues);
        std::cout << (dgtz->m_iEnableMask[0]) << " " << (dgtz->m_iEnableMask[1]) << "\n";

        std::cout << "Digitizer Vector size is  " << digitizers.size() << "\n";

    }
    
    // Set the synchronization mode
    ret = SetSyncMode(digitizers, &config);
    if (ret!=0) {
        std::cout <<"ERROR in setting the synchronization mode of the digitizers"<<std::endl;
        exit(EXIT_FAILURE);
    }
    
    //Allocate readout buffer
    int iTotBoardIndex = 0; //index for the total number of boards. It goes from 0 to iNTotBoards-1
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
    //the output file is set for each board
    //each file contains all the channels of the board


    


    FILE* event_file[iNTotBoards] = {NULL};
    for (int i = 0; i < iNTotBoards; i++){
        std::string eventFileName = sDataFullPath + "_board_" + std::to_string(i) + ".bin";
        std::cout << "Output file: " << eventFileName << '\n';
        event_file[i] = fopen(eventFileName.c_str(), "w");
    }
    // print out the output file names
    
    std::cout << "TOTAL NUMBER OF BOARDS: " << iNTotBoards << '\n';
    
    uint32_t iNumEventsAcquired[iNTotBoards] = {0};
    bool bAcquisitionStarted = false;
    uint32_t iBufferSize, iNumEvents = 0;
    uint64_t CurrentTime;
    uint64_t PrevRateTime[iNTotBoards];
    uint64_t ElapsedTime[iNTotBoards];
    uint32_t Nb[iNTotBoards]={0}, Ne[iNTotBoards]={0}; //number of bytes and events read from the board
    
    StartRun(digitizers, &config);
    for (int i = 0; i < iNTotBoards; i++) {
        PrevRateTime[i] = get_time();
    }
    // set the number of events to acquire. This should be a user input

    // The number of events acquired is set by the user

    uint64_t totalEvents = 0;
    // use the sum of the number of events acquired by all the boards
    while(totalEvents < iNEvts){
        iTotBoardIndex = 0;
        for (Digitizer* dgtz : digitizers) {
            for (int i = 0; i < dgtz->m_iNBoards; i++){
                ret = CAEN_DGTZ_ReadData(dgtz->m_iHandles[i], CAEN_DGTZ_SLAVE_TERMINATED_READOUT_MBLT, buffer[iTotBoardIndex], &iBufferSize);
                //PrintError(iTotBoardIndex, "Reading Events", "buffer", ret);
                //printf("reading from board %d\n", iTotBoardIndex);
                //printf("Buffer Size: %d\n",iBufferSize);

                //only write to file if the buffer is not empty
                //Otherwise, just to show the trigger rate
                if (iBufferSize != 0) {
                    ret = CAEN_DGTZ_GetNumEvents(dgtz->m_iHandles[i], buffer[iTotBoardIndex], iBufferSize, &iNumEvents); //iBuffersize and iNumEvents are modified by the function
                    //PrintError(iTotBoardIndex, "Getting Number of Events", "buffer", ret);
                    fwrite(buffer[iTotBoardIndex], 1, iBufferSize, event_file[iTotBoardIndex]);
                    Nb[iTotBoardIndex] += iBufferSize;
                    Ne[iTotBoardIndex] += iNumEvents;
                    iNumEventsAcquired[iTotBoardIndex] +=iNumEvents;
                    totalEvents += iNumEvents;
                }


                CurrentTime = get_time();
                ElapsedTime[iTotBoardIndex] = CurrentTime - PrevRateTime[iTotBoardIndex];

                // print the trigger rate every 1s
                if (ElapsedTime[iTotBoardIndex] > 1000) {
                    if (Nb[iTotBoardIndex] == 0)
                        if (ret == CAEN_DGTZ_Timeout) printf ("Timeout...\n"); else printf("No data from board %d\n", iTotBoardIndex);
                    else
                        printf("Reading from board %d at %.2f MB/s (Trg Rate: %.2f Hz)\n", iTotBoardIndex, (float)Nb[iTotBoardIndex]/((float)ElapsedTime[iTotBoardIndex]*1048.576f), (float)Ne[iTotBoardIndex]*1000.0f/(float)ElapsedTime[iTotBoardIndex]);
                        Nb[iTotBoardIndex] = 0;
                        Ne[iTotBoardIndex] = 0;
                        PrevRateTime[iTotBoardIndex] = CurrentTime;
                    }
                    // print the total number of events acquired
                    //printf("Acquired %d events\n", iNumEventsAcquired[iTotBoardIndex]);

                iTotBoardIndex++;
            }
        }
    }
    
    printf("Test done\n");
    StopRun(digitizers, &config);

    for (int i = 0; i < iNTotBoards; i++){
        fclose(event_file[i]);
    }
    
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

    return 0;
}