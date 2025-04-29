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

#include <TCanvas.h>
#include <TH1F.h>
#include <TSystem.h>
#include <TApplication.h>
#include <TGraph.h>
#include <TLegend.h>

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

    // std::map<std::string, int> boardTypeCount;
    // std::vector<std::string> boardTypes;
    std::vector<Digitizer*> digitizers;
    int iNTotBoards = config.sBoardTypes.size();
    char *buffer[iNTotBoards] = {nullptr};

    // // count digitizer types
    // for (const auto& bt : config.sBoardTypes) {
    //     boardTypeCount[bt]++;
    // }

    // // Print the unique digitizer types and their counts
    // for (const auto& pair : boardTypeCount) {
    //     boardTypes.push_back(pair.first);
    //     std::cout << "Board: " << pair.first << ", Count: " << pair.second << std::endl;
    // }


    //742 events are vastly different from the rest of the board types. Maybe later I'll do something that allocates events within the digitizer itself, but that just seems like extra overhead
    std::vector<CAEN_DGTZ_X742_EVENT_t*> Events742;
    std::map<int, int> nthx742Index;
    int n_x742 = 0;
    
    std::vector<CAEN_DGTZ_UINT16_EVENT_t*> Events16;
    std::map<int, int> nthFlashADCDigitizers; // These are flash ADC digitizers that have your usual, well behaved type of events with a <=16 bit adc
    int n_flashADC = 0;
    
    for (int i=0; i<config.iNBoards; i++) {
        if (config.sBoardTypes[i] == "V1725") {
            V1725* dgtz = new V1725(sConfigFile, config, i);
            digitizers.push_back(dgtz);
            ret = CAEN_DGTZ_AllocateEvent(dgtz->m_iHandle, (void**)&Events16[n_flashADC]);
            if (ret!=CAEN_DGTZ_Success){
                std::cout <<"ERROR: Failed to allocate event for the "<<n_flashADC<<"th flash ADC digitizer\n";
                return -1;
            }
            nthFlashADCDigitizers[i] = n_flashADC;
            n_flashADC++;
        }
        else if (config.sBoardTypes[i] == "V1742") {
            // config file parses the number of boards of this type
            V1742* dgtz = new V1742(sConfigFile, config, i);
            digitizers.push_back(dgtz);
            Events742.push_back(NULL);
            ret = CAEN_DGTZ_AllocateEvent(dgtz->m_iHandle, (void**)&Events742[n_x742]);
            if (ret!=CAEN_DGTZ_Success){
                std::cout <<"ERROR: Failed to allocate event for V1742 number "<<n_x742<<"\n";
                return -1;
            }
            nthx742Index[i] = n_x742;
            n_x742++;
        }
        //TO DO: Add else if statements for V1720s
    }

    // MAX_X742_GROUP_SIZE is defined in CAENDigitizer
    CAEN_DGTZ_DRS4Correction_t X742Tables[MAX_X742_GROUP_SIZE];

    for (Digitizer* dgtz : digitizers) {
        ret = dgtz->ProgramDigitizer();
        if (ret != 0){
            std::cout << "ERROR in programming one of the digitizers"<<std::endl;
            exit(EXIT_FAILURE);
        }
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
        std::cout <<"Allocating the readout buffers\n";
        ret |= CAEN_DGTZ_MallocReadoutBuffer(dgtz->m_iHandle, &buffer[iTotBoardIndex], &iAllocatedSize); 
        if (ret) {
            printf("Can't allocate memory for the acquisition\n");
            exit(EXIT_FAILURE);
        }
        else {
            printf("Allocated memory for board %d\n", iTotBoardIndex);
        }
        iTotBoardIndex++;
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
    uint32_t iBufferSize = 0, iNumEvents = 0;
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
    std::vector<std::queue<uint32_t>> NumEventsQueue(iNTotBoards);
    bool bPlotFlags = false;

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
                        ret = CAEN_DGTZ_ReadData(dgtz->m_iHandle, CAEN_DGTZ_SLAVE_TERMINATED_READOUT_MBLT, buffer[iTotBoardIndex], &iBufferSize);
                        PrintError(iTotBoardIndex, "Reading Events", "buffer", ret);
                        // printf("Buffer Size: %d\n",iBufferSize);
                        if (iBufferSize != 0) {
                            ret = CAEN_DGTZ_GetNumEvents(dgtz->m_iHandle, buffer[iTotBoardIndex], iBufferSize, &iNumEvents);
                            PrintError(iTotBoardIndex, "Getting Number of Events", "buffer", ret);

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
                                bPlotFlags=true;
                            }

                            if (iBufferSize != 0) {
                                //Push buffer to queue
                                char* DataChunk = (char*) std::malloc(iBufferSize);
                                std::memcpy(DataChunk, buffer[iTotBoardIndex], iBufferSize);
                                DigitizerBufferQueue[iTotBoardIndex].push(DataChunk);
                                BufferSizeQueue[iTotBoardIndex].push(iBufferSize);
                                NumEventsQueue[iTotBoardIndex].push(iNumEvents);
                            }

                        iTotBoardIndex++;
                    }
                }

                // Only check if the master board has crossed the number of event threshold
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
            TApplication *RootApp = new TApplication("App", &argc, argv);
            TCanvas *DaqCanvas = new TCanvas("c1", "Livetime DAQ plotter", 800, 600);
            TLegend *DaqLegend = new TLegend(0.7, 0.7, 0.9, 0.9);
            DaqCanvas->Update();

            int p_iTotBoardIndex = 0; //Board index for the processor

            //Make the legend
            for (Digitizer* dgtz : digitizers) {
                if (dgtz->m_iPlottingEnabled) {
                    for (int pch_i = 0; pch_i<dgtz->m_iPlottedChannels.size(); pch_i++){
                        int this_channel = dgtz->m_iPlottedChannels[pch_i];
                        std::stringstream legend_ss;
                        legend_ss<<"Board "<<p_iTotBoardIndex<<" Ch "<<this_channel;
                        DaqLegend->AddEntry(dgtz->m_Graphs[pch_i], legend_ss.str().c_str(), "l");
                    }
                }
                p_iTotBoardIndex++;
            }

            bool bQueuesEmpty=false;
            bool bFinishedPlotting=true;
            bool legendNotDrawn=true;
            while(!(runcontrol.quit && bQueuesEmpty)){
                p_iTotBoardIndex=0;
                int iTotalQueueSize = 0;

                // DaqLegend->Clear();
                for (Digitizer* dgtz : digitizers) {
                    //Check the queues
                    int queuelimit = (runcontrol.quit) ? 1 : 2; //If you've quit, there must be at least one element, otherwise, there must be two
                    iTotalQueueSize+=DigitizerBufferQueue[p_iTotBoardIndex].size();

                    if (DigitizerBufferQueue[p_iTotBoardIndex].size()>=queuelimit){
                        char* buf_from_q = DigitizerBufferQueue[p_iTotBoardIndex].front();
                        uint32_t buf_size_from_q = BufferSizeQueue[p_iTotBoardIndex].front();
                        uint32_t num_events_from_q = NumEventsQueue[p_iTotBoardIndex].front();

                        
                        for (int ev=0; ev<num_events_from_q; ev++){
                            ret = CAEN_DGTZ_GetEventInfo(dgtz->m_iHandle, buf_from_q, buf_size_from_q, ev, &EventInfo, &EventPtr);
                            if (dgtz->m_BoardType=="V1742") {
                                ret = CAEN_DGTZ_DecodeEvent(dgtz->m_iHandle, EventPtr, (void**)&Events742[nthx742Index[p_iTotBoardIndex]]);
                            }
                            else if (dgtz->m_bIsFlashADC){
                                ret = CAEN_DGTZ_DecodeEvent(dgtz->m_iHandle, EventPtr, (void**)&Events16[nthFlashADCDigitizers[p_iTotBoardIndex]]);
                            }
                            
                            if (ret!=CAEN_DGTZ_Success){
                                std::cout<<"ERROR: Could not decode 742 event!\n";
                            }
                        }
                        
                        // printf("%d\n", bPlotFlags);
                        if (bPlotFlags&&dgtz->m_iPlottingEnabled){
                            bFinishedPlotting = false;
                            DaqCanvas->cd();
                            
                            for (int pch_i = 0; pch_i<dgtz->m_iPlottedChannels.size(); pch_i++){
                                //TO DO: Make a mapping of the total board index to the index of the x742. For now, ALWAYS make the x742s go first
                                int this_channel = dgtz->m_iPlottedChannels[pch_i];
                                uint32_t samples_this_channel = 0;
                                int this_channel_group = 0;
                                int this_channel_index_group = 0;

                                if (dgtz->m_BoardType=="V1742"){
                                    this_channel_group = this_channel / 8; // Channels on the x742 are grouped into
                                    this_channel_index_group = this_channel % 8; // The channel index within a particular group
                                    samples_this_channel = Events742[nthx742Index[p_iTotBoardIndex]]->DataGroup[this_channel_group].ChSize[this_channel_index_group];
                                }
                                else if (dgtz->m_bIsFlashADC){
                                    samples_this_channel = Events16[nthFlashADCDigitizers[p_iTotBoardIndex]]->ChSize[this_channel];
                                }
                                
                                // printf("Has %d samples\n", samples_this_channel);
                                dgtz->m_Graphs[pch_i]->Set(samples_this_channel);
                                
                                for (int p_j=0; p_j<samples_this_channel; p_j++){
                                    dgtz->m_Graphs[pch_i]->SetPointX(p_j, p_j*dgtz->m_dDT);
                                    if (dgtz->m_BoardType=="V1742"){
                                        dgtz->m_Graphs[pch_i]->SetPointY(p_j, Events742[nthx742Index[p_iTotBoardIndex]]->DataGroup[this_channel_group].DataChannel[this_channel_index_group][p_j]);
                                    }
                                    else if (dgtz->m_bIsFlashADC){
                                        dgtz->m_Graphs[pch_i]->SetPointY(p_j, Events16[nthFlashADCDigitizers[p_iTotBoardIndex]]->DataChannel[this_channel][p_j]);
                                    }
                                }

                                dgtz->m_Graphs[pch_i]->SetLineColor(p_iTotBoardIndex+1);
                                // if (legendNotDrawn){
                                    // std::stringstream legend_ss;
                                    // legend_ss<<"Board "<<p_iTotBoardIndex<<" Ch "<<this_channel;
                                    // DaqLegend->AddEntry(dgtz->m_Graphs[i][pch_i], legend_ss.str().c_str(), "l");
                                // }

                                if ((p_iTotBoardIndex==0)&&(pch_i==0)) {
                                    dgtz->m_Graphs[pch_i]->Draw("AL");
                                    dgtz->m_Graphs[pch_i]->GetXaxis()->SetTitle("Time [ns]");
                                    dgtz->m_Graphs[pch_i]->GetYaxis()->SetTitle("Amplitude [ADC Counts]");
                                    dgtz->m_Graphs[pch_i]->SetMinimum(0);
                                    dgtz->m_Graphs[pch_i]->SetMaximum(1<<14);
                                }
                                else{
                                    dgtz->m_Graphs[pch_i]->Draw("L SAME");
                                }
                            }
                        }

                        fwrite(buf_from_q, 1, BufferSizeQueue[p_iTotBoardIndex].front(), event_file_test[p_iTotBoardIndex]);
                        DigitizerBufferQueue[p_iTotBoardIndex].pop();
                        BufferSizeQueue[p_iTotBoardIndex].pop();
                        NumEventsQueue[p_iTotBoardIndex].pop();
                        std::free(buf_from_q);
                    }

                    p_iTotBoardIndex++;
                }                
                


                DaqLegend->Draw();
                DaqCanvas->Update();
                // DaqLegend->Clear();
                if (!bFinishedPlotting) {
                    bPlotFlags = false;
                    bFinishedPlotting = true;
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
        CAEN_DGTZ_SWStopAcquisition(dgtz->m_iHandle);
        CAEN_DGTZ_FreeReadoutBuffer(&buffer[iTotBoardIndex]);
        if (dgtz->m_BoardType=="V1742"){
            CAEN_DGTZ_FreeEvent(dgtz->m_iHandle, (void**)&Events742[nthx742Index[iTotBoardIndex]]);
        }
        else if (dgtz->m_bIsFlashADC){
            CAEN_DGTZ_FreeEvent(dgtz->m_iHandle, (void**)&Events16[nthFlashADCDigitizers[iTotBoardIndex]]);
        }
        iTotBoardIndex++;
    }

    for (Digitizer* dgtz : digitizers) {
        delete dgtz;
    }

    digitizers.clear();

    return 0;
}