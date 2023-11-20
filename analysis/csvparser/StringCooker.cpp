#include <boost/algorithm/string.hpp>
#include "StringCooker.h"

namespace StringCooker {
    void strip_left(string &s, const char flag) {
        if (!s.empty() && s[0] == flag) {
            s = s.substr(1);
        }
    }

    void strip_right(string &s, const char flag) {
        if (!s.empty() && s[s.size() - 1] == flag) {
            s = s.substr(0, s.size() - 1);
        }
    }

    void strip(std::string &str, const char par) {
        strip_left(str, par);
        strip_right(str, par);
    }

    void clean_space(string& target_str) {
        boost::trim(target_str);
    }

    void clean_quotes(string& target_str) {
        if(!target_str.empty()) {
            if(target_str[0] == '"' || target_str[target_str.size()-1] == '"') {
                strip(target_str, '"');
            }
        }
    }

    string cook_export_string(const string &str) {
        string cooked_str;
        cooked_str += '"';
        for(size_t i = 0; i < str.size(); ++i) {
            if(str[i] != '"') {
                cooked_str += str[i];
            } else {
                cooked_str += "\\\"";
            }
        }
        cooked_str += '"';
        return cooked_str;
    }
}