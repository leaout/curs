#include <iostream>
#include <map>
#include <vector>
#include "csvparser/BaseDriver.h"

using namespace std;

struct Buddle {
    uint32_t time;
    uint32_t open;
    uint32_t high;
    uint32_t low;
    uint32_t close;
    uint32_t volume;
    uint64_t money;
};

class MemoryBuddle {
public:
    enum class Period {
        MIN1 = 0,
        MIN5,
        MIN15,
        MIN30,
        MIN60,
        DAY,
        WEEK,
        MONTH,
        SEASON,
        YEAR,
    };
private:
    map<pair<uint64_t, Period>, vector<Buddle>> m_data;
};

class DataManager {
    MemoryBuddle m_buddles;
public:
    void csv_loader() {

    }
};

int main() {
    shared_ptr<BaseSeoratorParser::BaseDriver> m_base_driver;
    m_base_driver = make_shared<BaseSeoratorParser::BaseDriver>("\t", "600519.txt", 10000, 0, 0, -1);
    vector<pair<size_t,Row>> data;
    while(m_base_driver->next(data)){
        std::cout << "row size:" << data.size() << std::endl;
    }
    std::cout << "hello quant!" << std::endl;
    return 0;
}

