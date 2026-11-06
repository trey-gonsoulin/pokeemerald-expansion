#include <filesystem>
#include <mutex>
#include <thread>
#include <fstream>
#include <iterator>
#include <algorithm>
#include "fileDispatcher.h"
#include "compressAlgo.h"

struct ThingCount {
    size_t number = 0;
    size_t count = 1;
};

bool isNumber(std::string input)
{
    return input.find_first_not_of("0123456789") == std::string::npos;
}

bool parseSetting(std::string argument, bool *pSetting)
{
    if (argument.compare("true") == 0)
        *pSetting = true;
    else if (argument.compare("false") == 0)
        *pSetting = false;
    else
    {
        fprintf(stderr, "Unrecognized setting \"%s\", expected \"true\" or \"false\"\n", argument.c_str());
        return false;
    }
    return true;
}

enum Option {
    WRITE,
    FRAME_WRITE,
    DECODE,
    USAGE,
};

int main(int argc, char *argv[])
{
    Option option = USAGE;
    bool printUsage = false;
    std::string input;
    std::string output;
    InputSettings settings(true, true, true);

    if (argc > 1)
    {
        std::string argument = argv[1];
        if (argument.compare("-w") == 0)
            option = WRITE;
        else if (argument.compare("-fw") == 0)
            option = FRAME_WRITE;
        else if (argument.compare("-d") == 0)
            option = DECODE;
    }
    switch (option)
    {
        case FRAME_WRITE:
            //  Not implemented yet
            fprintf(stderr, "Frame writing isn't implemented yet\n");
            settings.useFrames = true;
            option = WRITE;
            return 1;
        case WRITE:
            //  The input and output, then either no settings or all three
            if (argc == 4 || argc == 7)
            {
                input = argv[2];
                output = argv[3];
                if (argc == 7
                 && !(parseSetting(argv[4], &settings.canEncodeLO)
                   && parseSetting(argv[5], &settings.canEncodeSyms)
                   && parseSetting(argv[6], &settings.canDeltaSyms)))
                    printUsage = true;
            }
            else
            {
                printUsage = true;
            }
            break;
        case DECODE:
            if (argc == 4)
            {
                input = argv[2];
                output = argv[3];
            }
            else
            {
                printUsage = true;
            }
            break;
        case USAGE:
            printUsage = true;
            break;
    }
    if (printUsage)
    {
        fprintf(stderr, "Usage:\n\
                %s -w \"path/to/some/file.4bpp\" \"path/to/some/file.4bpp.smol\"\n\
                    Compresses the first argument and writes the result to the second argument.\n\
                This mode can also be appended with 3 true/false statements that control the following settings of the compression:\n\
                    - If the compression instructions can be tANS encoded.\n\
                    - If the raw symbols in the compression can be tANS encoded.\n\
                    - If the raw symbols in the compression can be delta encoded.\n\
                %s -d \"path/to/some/file.4bpp.smol\" \"path/to/some/file.4bpp\"\n\
                    Decompresses the first argument and writes it to the second argument.\n", argv[0], argv[0]);

        return 1;
    }

    if (option == WRITE)
    {
        if (std::filesystem::exists(input))
        {
            CompressedImage image;
            if (settings.useFrames)
                image = processImageFrames(input, settings);
            else
                image = processImage(input, settings);
            if (image.isValid)
            {
                std::ofstream fileOut(output.c_str(), std::ios::out | std::ios::binary);
                fileOut.write(reinterpret_cast<const char *>(image.writeVec.data()), image.writeVec.size()*4);
                fileOut.close();
                if (!fileOut)
                {
                    fprintf(stderr, "Failed to write %s\n", output.c_str());
                    return 1;
                }
            }
            else
            {
                fprintf(stderr, "Failed to compress image %s\n", input.c_str());
                return 1;
            }
        }
        else
        {
            fprintf(stderr, "Input file %s doesn't exist\n", input.c_str());
            return 1;
        }
    }
    if (option == DECODE)
    {
        if (std::filesystem::exists(input))
        {
            std::vector<unsigned int> inData;
            if (!readFileAsUInt(input, &inData))
            {
                return 1;
            }
            std::vector<unsigned short> image4bpp;
            if (!readRawDataVecs(&inData, &image4bpp))
            {
                fprintf(stderr, "Failed to decode %s\n", input.c_str());
                return 1;
            }
            std::vector<unsigned char> charVec(image4bpp.size()*2);
            for (size_t i = 0; i < image4bpp.size(); i++)
            {
                charVec[2*i] = image4bpp[i] & 0xff;
                charVec[2*i + 1] = (image4bpp[i] >> 8) & 0xff;
            }
            std::ofstream fileOut(output.c_str(), std::ios::out | std::ios::binary);
            std::copy(charVec.begin(), charVec.end(), std::ostreambuf_iterator<char>(fileOut));
            fileOut.close();
            if (!fileOut)
            {
                fprintf(stderr, "Failed to write %s\n", output.c_str());
                return 1;
            }
        }
        else
        {
            fprintf(stderr, "Input file %s doesn't exist\n", input.c_str());
            return 1;
        }
    }

    return 0;
}
