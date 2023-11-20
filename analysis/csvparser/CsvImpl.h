#ifndef CSV_PARSER_H
#define CSV_PARSER_H

#include <iostream>
#include <vector>
#include <mutex>
#include <condition_variable>
// boost headers
#include <boost/thread/pthread/shared_mutex.hpp>


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
    const vector<pair<size_t,Row>>& lines();
    size_t part_size_byte();
    bool dealt_and_deal();
    bool dealt();
private:
    vector<pair<size_t,Row>> m_lines;
    size_t m_part_size = 0;

private:
    Row m_cur_line;
    bool m_dealt = false;
    boost::shared_mutex m_deal_mtx;
};


#endif //CSV_PARSER_H
