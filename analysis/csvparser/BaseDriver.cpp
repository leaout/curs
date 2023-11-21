#include "BaseDriver.h"
#include "SepratorScanner.h"
#include "CsvImpl.h"
#include "SepratorParser.h"

namespace BaseSeoratorParser {

    using namespace std;

    void BaseDriver::error(const class location& l,
                           const std::string& m,
                           const int& err_code) {

        m_error_msg.clear();
        std::string msg(m);
        m_error_msg << msg << std::endl;
        cerr << m_error_msg.str() << endl;
    }

    bool BaseDriver::start() {
//        m_file_stream.open(m_file);
        bool result = parse_stream(m_file_stream, "csv");

        return result;
    }
    bool BaseDriver::next(vector<pair<size_t,Row>>& row_values){
        if(!m_file_stream.is_open()){
            return false;
        }
        bool result = parse_stream(m_file_stream, "csv");
        if(result && m_csv_impl->lines().size()) {
            m_csv_impl->lines().swap(row_values);
            return result;
        } else{
            return false;
        }
    }
    bool BaseDriver::parse_stream(std::istream& in, const std::string& sname)
    {
        // clear the error msg in every begining
        m_error_msg.clear();
        m_stream_name = sname;
        int ret;
        BaseSeoratorParser::SepratorScanner scanner(&in);
        in.seekg(m_file_offset);
        scanner.set_debug(trace_scanning);
        this->seprator_lexer = &scanner;
        BaseSeoratorParser::SepratorParser parser(*this);
        parser.set_debug_level(trace_parsing);

        m_csv_impl = make_shared<CsvImpl>(m_partition_size);

        ret = parser.parse();

        if(ret != 0) {
            cerr << "parse csv error, line:" << m_scan_line_count << endl;
            return false;
        }

        return ret==0;

    }

    void BaseDriver::push_line_value(const string &value) {
        m_csv_impl->push_line_value(value);
    }

    bool BaseDriver::push_line() {
        // 跳过前skip行 从skip+1行开始
        m_scan_line_count++;
        if(m_scan_line_count <= m_skip) {
            m_csv_impl->drop_line();
            // return true means continue
            return true;
        }
        // limit == -1 导入全部
        // limit != -1 扫描limit条就结束（非成功limit条）
        if(m_limit != -1 && m_scan_line_count > m_skip && m_scan_line_count - m_skip > m_limit) {
            // return false measn do not continue
            return false;
        }
        m_csv_impl->push_line(m_scan_line_count);

        if(m_csv_impl->size() >= m_partition_size) {

        }
        return true;
    }


    void BaseDriver::parse_escape_character(std::string &target_str) {
        unordered_map<string, string> escape_character_dictionary = {
                {"'", "\x27"},
                {"\"", "\x22"},
                {"?", "\x3f"},
                {"\\", "\x5c"},
                {"a", "\x07"},
                {"b", "\x08"},
                {"f", "\x0c"},
                {"n", "\x0a"},
                {"r", "\x0d"},
                {"t", "\x09"},
                {"v", "\x0b"}
        };
        string escape_character_parsed_str;
        for(size_t i = 0; i < target_str.size(); ) {
            if(target_str[i] == '\\') {
                if(i+1 < target_str.size()) {
                    string key;
                    key += target_str[i+1];
                    auto it  = escape_character_dictionary.find(key);
                    if(it != escape_character_dictionary.end()) {
                        escape_character_parsed_str += (it->second);
                        i += 2;
                    } else {
                        // pass this '\'
                        ++i;
                    }
                } else {
                    // pass this '\'
                    ++i;
                }
            } else {
                escape_character_parsed_str += target_str[i];
                ++i;
            }
        }
        std::swap(escape_character_parsed_str, target_str);
    }
}

