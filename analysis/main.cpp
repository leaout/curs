#include <iostream>
#include <map>
#include <vector>
using namespace std;

struct Buddle{
    uint32_t time;
    uint32_t open;
    uint32_t close;
    uint32_t high;
    uint32_t low;
    uint32_t volume;
    uint64_t money;
};
class MemoryBuddle{
public:
    enum class Period{
        MIN1 = 0,
        MIN5 ,
        MIN15 ,
        MIN30 ,
        MIN60 ,
        DAY ,
        WEEK ,
        MONTH,
        SEASON,
        YEAR,
    };
private:
    map<pair<uint64_t,Period>,vector<Buddle>> m_data;
};
class DataManager{
public:
    void buddle_loader(){

    }
};

int main() {
    std::cout << "hello quant!" << std::endl;
    return 0;
}

