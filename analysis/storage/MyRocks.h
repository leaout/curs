#ifndef MY_ROCKS_H
#define MY_ROCKS_H

#include <iostream>
#include <mutex>
#include <string>
#include <thread>

#include "rocksdb/db.h"
#include "rocksdb/utilities/transaction.h"
#include "rocksdb/utilities/transaction_db.h"
#include "rocksdb/table.h"
#include "rocksdb/filter_policy.h"
#include "rocksdb/merge_operator.h"

using namespace std;
using namespace rocksdb;

class MyRocks {
public:
    MyRocks();

    virtual ~MyRocks();

public:
    //common functions
    rocksdb::Status init(const string &db_path_name) ;

    //write
    rocksdb::Status write(const string &cf_name,
                  const rocksdb::Slice &key,
                  const rocksdb::Slice &value) ;

    rocksdb::Status write(shared_ptr<rocksdb::Transaction> transaction,
                  const string &cf_name,
                  const rocksdb::Slice &key,
                  const rocksdb::Slice &value) ;

    rocksdb::Status default_write(const rocksdb::Slice &key,
                          const rocksdb::Slice &value) ;

    rocksdb::Status default_write(shared_ptr<rocksdb::Transaction> transaction,
                          const rocksdb::Slice &key,
                          const rocksdb::Slice &value) ;

    //batch
    rocksdb::Status add_put_batch(rocksdb::WriteBatch &batch,
                          const string &cf_name,
                          const rocksdb::Slice &key,
                          const rocksdb::Slice &value) ;

    rocksdb::Status add_default_put_batch(rocksdb::WriteBatch &batch,
                                  const rocksdb::Slice &key,
                                  const rocksdb::Slice &value) ;

    rocksdb::Status add_merge_batch(rocksdb::WriteBatch &batch,
                            const string &cf_name,
                            const rocksdb::Slice &key,
                            const rocksdb::Slice &value) ;

    rocksdb::Status add_default_merge_batch(rocksdb::WriteBatch &batch,
                                    const rocksdb::Slice &key,
                                    const rocksdb::Slice &value) ;

    rocksdb::Status add_delete_batch(rocksdb::WriteBatch &batch,
                             const string &cf_name,
                             const rocksdb::Slice &key) ;

    rocksdb::Status add_default_delete_batch(rocksdb::WriteBatch &batch,
                                     const rocksdb::Slice &key) ;

    rocksdb::Status write_batch(rocksdb::WriteBatch &batch) ;

    //merge
    rocksdb::Status merge(const string &cf_name,
                  const rocksdb::Slice &key,
                  const rocksdb::Slice &value) ;

    rocksdb::Status merge(shared_ptr<rocksdb::Transaction> transaction,
                  const string &cf_name,
                  const rocksdb::Slice &key,
                  const rocksdb::Slice &value) ;

    //read
    rocksdb::Status read(const string &cf_name,
                 const rocksdb::Slice &key,
                 string &out_value) ;

    rocksdb::Status default_read(const rocksdb::Slice &key,
                         string &out_value) ;

    vector<rocksdb::Status> multi_read(const string &cf_name,
                               const std::vector<rocksdb::Slice> &keys,
                               vector<string> &out_value) ;

    //delete
    rocksdb::Status delete_key(const string &cf_name,
                       const rocksdb::Slice &key) ;

    rocksdb::Status delete_key(shared_ptr<rocksdb::Transaction> transaction,
                       const string &cf_name,
                       const rocksdb::Slice &key) ;

    rocksdb::Status default_delete_key(const rocksdb::Slice &key) ;

    rocksdb::Status default_delete_key(shared_ptr<rocksdb::Transaction> transaction,
                               const rocksdb::Slice &key) ;

    rocksdb::Status delete_range(const string &cf_name,
                         const rocksdb::Slice &begin_id,
                         const rocksdb::Slice &end_id) ;
    rocksdb::Status default_delete_range(const rocksdb::Slice &begin_id,
                                const rocksdb::Slice &end_id) ;

    //iterator
    rocksdb::Iterator *new_iterator(const string &cf_name) ;

    rocksdb::Iterator *new_default_iterator() ;

    rocksdb::ColumnFamilyHandle *exist_column_family(const string &cf_name) ;

    void flush() ;


    //backup/restore
    rocksdb::Status back_up(const string backup_path) ;

    rocksdb::Status restore(const string restore_path) ;




    rocksdb::Status ingest_sstfile(const string &cf_name,
                           const vector<string> &sst_files_path) ;

    rocksdb::Status list_cf_names(std::vector<std::string> &out_cf_names) ;
    rocksdb::Status drop() ;
private:

    rocksdb::Status create_db_by_existed_cf(const std::vector<std::string> &exists_column_families, bool read_only = false);

    rocksdb::Status create_cf(const string &cf_name);

private:
    rocksdb::DB *m_db = nullptr;
    std::string m_path;
    map<string, rocksdb::ColumnFamilyHandle *> m_map_handles; // column -> handle
    rocksdb::Options m_options;
    rocksdb::ReadOptions m_read_options;
    rocksdb::WriteOptions m_write_options;
    rocksdb::ColumnFamilyOptions m_column_family_options;
    bool m_drop = false;
};


#endif

