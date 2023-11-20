
#ifndef CSV_PARSER_DRIVER_1_H
#define CSV_PARSER_DRIVER_1_H

#include <string>
#include <fstream>
#include <sstream>
#include <iostream>
#include <vector>
#include <queue>
#include <boost/algorithm/string.hpp>
#include "location.hh"
#include "CsvImpl.h"

namespace BaseSeoratorParser {
    using namespace std;
    class BaseDriver {
    public:
        BaseDriver(string seprator, const string &file, int partition_size,
                   size_t file_offset, long long skip, long long limit)
                : m_file(file), m_seprator(seprator),
                  m_partition_size(partition_size),
                  m_file_offset(file_offset),
                  m_skip(skip),
                  m_limit(limit) {
            if (file_offset > 0) {
                m_scan_line_count = 1;
            }
        }

        bool start();

    public:
        class SepratorScanner *seprator_lexer = NULL;

        void push_line_value(const string &value);
        bool push_line();
        bool parse_stream(std::istream& in, const std::string& sname);
        void parse_escape_character(std::string &target_str);

        void error(const class location &l, const std::string &m, const int &err_code);

        std::string m_stream_name;
        string m_seprator = ",";
        BaseSeoratorParser::location m_location;

    private:
        std::ostringstream m_error_msg;
        bool trace_scanning = false;
        bool trace_parsing = false;


        string m_file;
        std::ifstream m_file_stream;

        shared_ptr<CsvImpl> m_csv_impl = NULL;
        size_t m_partition_size = 10000;
        size_t m_file_offset = 0;
        size_t m_scan_line_count = 0;
        long long m_skip = 0;
        long long m_limit = -1;
    };

} // namespace example

#endif //CSV_PARSER_DRIVER_1_H
