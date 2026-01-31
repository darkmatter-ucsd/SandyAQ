#include <CAENDigitizer.h>
#include <iostream>

int main(){
    //Open the digitizers
    int ret=0;
    uint32_t reg;
    int handle[2];
    for (int i=0; i<2; i++){
        ret = CAEN_DGTZ_OpenDigitizer(CAEN_DGTZ_OpticalLink, 0, i, 0, &handle[i]);
        ret |= CAEN_DGTZ_Reset(handle[i]);
        printf("Ret %d: Reset digitizer %d\n", ret, i);

        ret |= CAEN_DGTZ_WriteRegister(handle[i], CAEN_DGTZ_BOARD_ID_ADD, (i & 0x1));
        printf("Ret %d: Programmed board ID for digitizer %d\n", ret, i);

        // if (Params.TestPattern) {
        // ret |= CAEN_DGTZ_ReadRegister(handle[i], CAEN_DGTZ_BROAD_CH_CONFIGBIT_SET_ADD, &reg);
        // reg |= 1 << 3;
        // ret |= CAEN_DGTZ_WriteRegister(handle[i], CAEN_DGTZ_BROAD_CH_CONFIGBIT_SET_ADD, reg);
        // printf("Ret %d: Set test pattern for digitizer %d\n", ret, i);
        // }

        // if (Params.DRS4Frequency) {
        ret |= CAEN_DGTZ_SetDRS4SamplingFrequency(handle[i], CAEN_DGTZ_DRS4_5GHz);
        printf("Ret %d: Set DRS4 sampling frequency for digitizer %d\n", ret, i);
        // }

        ret |= CAEN_DGTZ_SetRecordLength(handle[i], 1024);
        printf("Ret %d: Set record length for digitizer %d\n", ret, i);
        ret |= CAEN_DGTZ_SetPostTriggerSize(handle[i], 50);
        printf("Ret %d: Set post trigger for digitizer %d\n", ret, i);
        ret |= CAEN_DGTZ_SetIOLevel(handle[i], CAEN_DGTZ_IOLevel_NIM);
        printf("Ret %d: Set FPIO for digitizer %d\n", ret, i);
        ret |= CAEN_DGTZ_SetMaxNumEventsBLT(handle[i], 255);
        printf("Ret %d: Set max num events BLT for digitizer %d\n", ret, i);

        //gr = Params.RefChannel[i] / 8;
        ret |= CAEN_DGTZ_SetGroupEnableMask(handle[i], 0xF);
        //ret |= CAEN_DGTZ_SetGroupEnableMask(handle[i], 1 << gr);

        printf("Ret %d: Set group enable mask for digitizer %d\n", ret, i);
        for (int gr = 0; gr < 4; ++gr) {
            ret |= CAEN_DGTZ_SetGroupFastTriggerThreshold(handle[i], gr, 10000);
            ret |= CAEN_DGTZ_SetGroupFastTriggerDCOffset(handle[i], gr, 10000);
            ret |= CAEN_DGTZ_SetTriggerPolarity(handle[i], gr, CAEN_DGTZ_TriggerOnFallingEdge);
            printf("Ret %d: Set group %d trigger settings for digitizer %d\n", ret, gr, i);
        }
        ret |= CAEN_DGTZ_SetFastTriggerDigitizing(handle[i], CAEN_DGTZ_ENABLE);
        ret |= CAEN_DGTZ_SetFastTriggerMode(handle[i], CAEN_DGTZ_TRGMODE_ACQ_ONLY);
        printf("Ret %d: Set fast trigger for digitizer %d\n", ret, i);


        ret |= CAEN_DGTZ_SetChannelDCOffset(handle[i], 1, 10000);
        printf("Ret %d: Set DC offsets for digitizer %d\n", ret, i);        if (ret){
            std::cout<<"ERROR: Could not open digitizer, error code "<<ret<<std::endl;
        }
        else{
            std::cout<<"Successfully opened digitizer "<<i<<"\n";
        }
    }

    

    for (int i=0; i<2; i++){
        ret = CAEN_DGTZ_CloseDigitizer(handle[i]);
        if (ret){
            std::cout<<"ERROR: Could not closer digitizer, error code "<<ret<<std::endl;
        }
        else{
            std::cout<<"Successfully closed digitizer "<<i<<"\n";
        }
    }

    return 0;
}