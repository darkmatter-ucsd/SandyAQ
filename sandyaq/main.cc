#include "Ini.hh"
#include "V1725.hh"
// #include "Utils.hh"
#include "CommonConfig.hh"
#include <getopt.h>
#include <string>
#include <vector>
#include <iostream>

int main(int argc, char* argv[]) {
    int c = 0;
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

    V1725 *digitizer = new V1725(sConfigFile, config, 0);
    PrintVec1d(digitizer->m_sLinkTypes);
    PrintVec2d(digitizer->m_iLinkValues);
    std::cout << (digitizer->m_iEnableMask[0]) << " " << (digitizer->m_iEnableMask[1]) << "\n";

    digitizer->ProgramDigitizers();

    // printf(SetSyncMode(digitizer->m_iHandles));

    delete digitizer;

    return 0;
}