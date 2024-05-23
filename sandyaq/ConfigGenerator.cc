#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <cstdlib>
#include <unistd.h>

using namespace std;

int main(int argc, char* argv[]) {
    int option = 0;
    int boardNumber = -1;
    int channelNumber = -1;
    int threshold = -1;
    string templateFile;
    string outputPath = "./";

    while ((option = getopt(argc, argv, "b:c:t:f:p:")) != -1) {
        switch (option) {
            case 'b':
                boardNumber = atoi(optarg);
                cout << "Board number: " << boardNumber << '\n';
                break;
            case 'c':
                channelNumber = atoi(optarg);
                cout << "Channel number: " << channelNumber << '\n';
                break;
            case 't':
                threshold = atoi(optarg);
                cout << "Threshold: " << threshold << '\n';
                break;
            case 'f':
                templateFile = optarg;
                cout << "Template file: " << templateFile << '\n';
                break;
            case 'p':
                outputPath = optarg;
                cout << "Output path: " << outputPath << '\n';
                break;
            default:
                cout << "Usage: ./generate_config -b <board_number> -c <channel_number> -t <threshold_value> -f <template_file> -p <output_path>" << endl;
                return 1;
        }
    }

    if (boardNumber == -1 || channelNumber == -1 || threshold == -1 || templateFile.empty()) {
        cout << "Missing required arguments." << endl;
        cout << "Usage: ./config_generator -b <board_number> -c <channel_number> -t <threshold_value> -f <template_file> -p <output_path> (optional)" << endl;
        return 1;
    }

    // Generate the output filename based on board, channel, and threshold
    stringstream ss;
    ss << outputPath << "/config_board" << boardNumber << "_channel" << channelNumber << "_threshold" << threshold << ".ini";
    string outputFilename = ss.str();

    ifstream inputFile(templateFile);
    ofstream outputFile(outputFilename);

    if (!inputFile || !outputFile) {
        cout << "Failed to open file(s)." << endl;
        return 1;
    }

    string line;
    bool inTargetBoard = false;
    bool channelSectionAdded = false;

    while (getline(inputFile, line)) {
        if (line.find("[BOARD-" + to_string(boardNumber) + "]") != string::npos) {
            inTargetBoard = true;
        } else if (inTargetBoard && line.find("[BOARD-") != string::npos) {
            if (!channelSectionAdded) {
                outputFile << "[BOARD-" << boardNumber << "_CHANNEL-" << channelNumber << "]" << endl;
                outputFile << "DC_OFFSET = +40" << endl;
                outputFile << "TRIGGER_THRESHOLD = " << threshold << endl;
                outputFile << "CHANNEL_TRIGGER = ACQUISITION_ONLY" << endl;
                outputFile << "PULSE_POLARITY = 1" << endl;
                channelSectionAdded = true;
            }
            inTargetBoard = false;
        }

        if (inTargetBoard) {
            if (line.find("CHANNEL_LIST") != string::npos) {
                size_t pos = line.find("=");
                if (pos != string::npos) {
                    line = line.substr(0, pos + 1) + " " + to_string(channelNumber);
                }
            }
        }

        outputFile << line << endl;
    }

    if (inTargetBoard && !channelSectionAdded) {
        outputFile << "[BOARD-" << boardNumber << "_CHANNEL-" << channelNumber << "]" << endl;
        outputFile << "DC_OFFSET = +40" << endl;
        outputFile << "TRIGGER_THRESHOLD = " << threshold << endl;
        outputFile << "CHANNEL_TRIGGER = ACQUISITION_ONLY" << endl;
        outputFile << "PULSE_POLARITY = 1" << endl;
    }

    inputFile.close();
    outputFile.close();

    cout << "Temporary config file generated: " << outputFilename << endl;

    return 0;
}