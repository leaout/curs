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
class MemoryBuddle {
public:
    map<pair<uint64_t, Period>, vector<Buddle>> m_data;
};

class DataManager {
public:
    MemoryBuddle m_buddles;
    void csv_loader() {

    }
};

struct Order{
    enum class OrderType{
        None,
        Buy,
        Sell
    };
    OrderType order_type;
    uint64_t order_id;
    uint64_t volume;
    uint64_t amt;
    double price = 0;
};
struct IndicatorOut{
    vector<double> outs;
};
class Indicator {
protected:
    DataManager *m_data_mgr;
public:
    virtual ~Indicator(){}
    Indicator(DataManager *intor) : m_data_mgr(intor) {

    }
    virtual size_t OutParamCount() = 0;
    virtual void get_indicator(vector<IndicatorOut>& intor_outs) = 0;
};
class Context{
public:

};
class Strategy{
protected:
    Context *m_ctx;
public:
    virtual ~Strategy(){}
    virtual void init( Context *ctx){
        m_ctx = ctx;
    }
    virtual void handle_tick(){

    }
    virtual void handle_bar(const Buddle& bar){

    }
    virtual void handle_end(){

    }
};
class Engine{
    std::shared_ptr<DataManager> m_data_mgr;
public:
    void init(std::shared_ptr<DataManager> data_mgr){
        m_data_mgr = data_mgr;
    }
    void run(Strategy* stg, int thread_num = 1){
        auto& his_data = m_data_mgr->m_buddles.m_data;
        for(auto&stock : his_data){
            for(auto& buddle : stock.second){
                stg->handle_bar(buddle);
            }
            stg->handle_end();
        }
    }
};

int main() {
    shared_ptr<BaseSeoratorParser::BaseDriver> m_base_driver;
    m_base_driver = make_shared<BaseSeoratorParser::BaseDriver>("\t", "600519.txt", 100, 0, 0, -1);
    vector<pair<size_t,Row>> data;
    while(m_base_driver->next(data)){
        std::cout << "row size:" << data.size() << std::endl;
    }
    std::cout << "hello quant!" << std::endl;
    return 0;
}

