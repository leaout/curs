#ifndef STRINGCOOKER_H
#define STRINGCOOKER_H

#include <string>
#include <boost/algorithm/string.hpp>

using namespace std;

namespace StringCooker {
    void strip_left(string &s, const char flag);
    void strip_right(string &s, const char flag);
    void strip(std::string &str, const char par);
    void clean_quotes(string& target_str);
    void clean_space(string& target_str);
    string cook_export_string(const string &str);
}


#endif //STRINGCOOKER_H
