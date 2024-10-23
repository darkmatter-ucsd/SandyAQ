#ifndef UTILS_HH
#define UTILS_HH

//****************************************************************************
// Some register addresses
//****************************************************************************
#define ADDR_GLOBAL_TRG_MASK     0x810C
#define ADDR_TRG_OUT_MASK        0x8110
#define ADDR_FRONT_PANEL_IO_SET  0x811C
#define ADDR_ACQUISITION_MODE    0x8100
#define ADDR_EXT_TRG_INHIBIT     0x817C
#define ADDR_RUN_DELAY           0x8170
#define ADDR_FORCE_SYNC			 0x813C
#define ADDR_RELOAD_PLL			 0xEF34
#define ADDR_GROUP_TRG_MASK      0x10A8

//****************************************************************************
// Run Modes
//****************************************************************************
// start on software command 
#define RUN_START_ON_SOFTWARE_COMMAND     0xC 
// start on S-IN level (logical high = run; logical low = stop)
#define RUN_START_ON_SIN_LEVEL            0xD
// start on first TRG-IN or Software Trigger 
#define RUN_START_ON_TRGIN_RISING_EDGE    0xE
// start on LVDS I/O level
#define RUN_START_ON_LVDS_IO              0xF

//Standard library
#include <iostream>
#include <vector>
#include <string>
#include <unistd.h>
#include <stdlib.h>
#include <termios.h>

//CAEN libraries
#include <CAENDigitizer.h>

//Internal headers
#include "CommonConfig.hh"

typedef struct RunControlVars_t {
    int quit;
    int restart;
    int start;
    int acquiring;
};

static struct termios g_old_kbd_mode;

template<typename T>
static void PrintVec1d(std::vector<T> &tArray){
    std::cout << "[";
    for (int j = 0; j<tArray.size(); j++){
        std::cout << tArray[j];
        if (j!=tArray.size()-1)
            std::cout << ",";
    }
    std::cout << "]\n";
}

template<typename T>
static void PrintVec2d(std::vector<T> &tArray){
    std::cout << "[";
    for (int i = 0; i < tArray.size(); i++){
        std::cout << "[";
        for (int j = 0; j<tArray[i].size(); j++){
            std::cout << tArray[i][j];
            if (j!=tArray[i].size()-1)
                std::cout << ",";
        }
        std::cout << "]";
        if (i!=tArray.size()-1)
            std::cout<<"\n";
    }
    std::cout<<"]\n";
}

static int CheckBoardFailureStatus(int handle, CAEN_DGTZ_BoardInfo_t BoardInfo) {

	int ret = 0;
	uint32_t status = 0;
	ret = CAEN_DGTZ_ReadRegister(handle, 0x8104, &status);
	if (ret != 0) {
		printf("Error: Unable to read board failure status.\n");
		return -1;
	}
    
	//read twice (first read clears the previous status)
	ret = CAEN_DGTZ_ReadRegister(handle, 0x8104, &status);
	if (ret != 0) {
		printf("Error: Unable to read board failure status.\n");
		return -1;
	}

	if(!(status & (1 << 7))) {
		printf("Board error detected: PLL not locked.\n");
		return -1;
	}

	return 0;
}

static void PrintError(int BoardNum, const char* Action, const char* Quantity, int ret) {
    if (ret) std::cout << "Error in "<<Action<<" the "<<Quantity<<" for board " << BoardNum << "\n";
}

/* Get time in milliseconds from the computer internal clock */
static double get_time(){
    long time_ms;
#ifdef WIN32
    struct _timeb timebuffer;
    _ftime( &timebuffer );
    time_ms = (long)timebuffer.time * 1000 + (long)timebuffer.millitm;
#else
    struct timeval t1;
    struct timezone tz;
    gettimeofday(&t1, &tz);
    time_ms = (t1.tv_sec) * 1000 + t1.tv_usec / 1000;
#endif
    return time_ms;
}

/*Keyboard hit handling*/

static void cooked(void)
{
	tcsetattr(0, TCSANOW, &g_old_kbd_mode);
}

static void raw(void)
{
	static char init;
/**/
	struct termios new_kbd_mode;

	if(init)
		return;
/* put keyboard (stdin, actually) in raw, unbuffered mode */
	tcgetattr(0, &g_old_kbd_mode);
	memcpy(&new_kbd_mode, &g_old_kbd_mode, sizeof(struct termios));
	new_kbd_mode.c_lflag &= ~(ICANON | ECHO);
	new_kbd_mode.c_cc[VTIME] = 0;
	new_kbd_mode.c_cc[VMIN] = 1;
	tcsetattr(0, TCSANOW, &new_kbd_mode);
/* when we exit, go back to normal, "cooked" mode */
	atexit(cooked);

	init = 1;
}

static int kbhit()
{
	struct timeval timeout;
	fd_set read_handles;
	int status;

	raw();
    /* check stdin (fd 0) for activity */
	FD_ZERO(&read_handles);
	FD_SET(0, &read_handles);
	timeout.tv_sec = timeout.tv_usec = 0;
	status = select(0 + 1, &read_handles, NULL, NULL, &timeout);
	if(status < 0)
	{
		printf("select() failed in kbhit()\n");
		exit(1);
	}
    return (status);
}

static int getch(void)
{
	unsigned char temp;

	raw();
    /* stdin = fd 0 */
	if(read(0, &temp, 1) != 1)
		return 0;
	return temp;

}

static void CheckKeyboardCommands(RunControlVars_t* runcontrol){
    int c=0;
    if (!kbhit())
        return;

    c = getch();

    switch(c) {
        case 'q':
            runcontrol->quit=1;
            break;
        case 'R':
            runcontrol->restart=1;
            break;
        case 's':
            if (!(runcontrol->start))
                runcontrol->start=1;
            else
                runcontrol->start=0;
                runcontrol->acquiring=0;
            break;
        default:
            break;
    }
}

#endif