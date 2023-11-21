#include "CsvImpl.h"

CsvImpl::CsvImpl(size_t line_count) {
    m_lines.reserve(line_count);
}

void CsvImpl::push_line_value(const string &value) {
    m_cur_line.emplace_back(std::move(value));
}

void CsvImpl::push_line(size_t line_num) {
    if(!m_cur_line.empty()) {
        if(m_cur_line.size() == 1 && m_cur_line.front().empty()) {
        } else {
            m_lines.emplace_back(make_pair(line_num,std::move(m_cur_line)));
        }

        Row().swap(m_cur_line);
    }
}

void CsvImpl::drop_line() {
    Row().swap(m_cur_line);
}

size_t CsvImpl::size() {
    return m_lines.size();
}


void CsvImpl::set_part_size_byte(size_t size_byte) {
    m_part_size = size_byte;
}

vector<pair<size_t,Row>>& CsvImpl::lines() {
    return m_lines;
}

size_t CsvImpl::part_size_byte() {
    return m_part_size;
}