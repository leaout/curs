#ifndef CSV_PARSER_H
#define CSV_PARSER_H

#include <iostream>
#include <vector>
#include <mutex>
#include <condition_variable>

using namespace std;
typedef std::vector<std::string> Row;
struct CsvImpl {
public:
    CsvImpl(size_t line_count);

public:
    void push_line_value(const string &value);
    void push_line(size_t line_num);
    void drop_line();
    size_t size();
    void set_part_size_byte(size_t size_byte);
    vector<pair<size_t,Row>>& lines();
    size_t part_size_byte();
private:
    vector<pair<size_t,Row>> m_lines;
    size_t m_part_size = 0;

private:
    Row m_cur_line;
};


#endif //CSV_PARSER_H
