#include <boost/filesystem.hpp>
#include "rocksdb/convenience.h"
#include "MyRocks.h"

MyRocks::MyRocks(){
    m_options.IncreaseParallelism(thread::hardware_concurrency());
    m_options.create_if_missing = true;
    m_options.OptimizeLevelStyleCompaction();
}

MyRocks::~MyRocks() {
    if (m_db != nullptr) {
        for (auto &handle : m_map_handles) {
            m_db->DestroyColumnFamilyHandle(handle.second);
        }
        CancelAllBackgroundWork(m_db, true);
        auto r_status = m_db->Close();
        if (r_status.ok()) {
            delete m_db;
        } else {
        }
    }
    m_db = nullptr;
    if(m_drop){
    }
}

rocksdb::Status MyRocks::drop() {
    m_drop = true;
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::init(const string &db_path_name) {
    m_path = db_path_name;

    m_options.target_file_size_base = 256 << 20;
    m_options.max_background_compactions = std::thread::hardware_concurrency();
    m_options.max_background_flushes = 2;
    m_options.keep_log_file_num = 6;
    m_options.max_log_file_size = 10<<20; //10 MB

    m_read_options.readahead_size = 64 << 20;

    //1.get exist column name
    std::vector<std::string> exists_column_families;
    list_cf_names(exists_column_families);

    //2.open db
    rocksdb::Status ret_status;
    if (exists_column_families.size() > 0) {
        ret_status = create_db_by_existed_cf(exists_column_families, false);
        if (!ret_status.ok())
            return ret_status;
    } else {
        exists_column_families.emplace_back("default");
        ret_status = create_db_by_existed_cf(exists_column_families, false);
        if (!ret_status.ok())
            return ret_status;

    }
    return ret_status;
}


rocksdb::Status MyRocks::list_cf_names(vector<string> &out_cf_names) {
    rocksdb::Status status = rocksdb::DB::ListColumnFamilies(m_options, m_path, &out_cf_names);
    if (!status.ok()) {
        return status;
    }
    return rocksdb::Status::OK();
}

rocksdb::ColumnFamilyHandle *MyRocks::exist_column_family(const string &cf_name) {
    auto find_it = m_map_handles.find(cf_name);
    if (find_it == m_map_handles.end()) {
        return nullptr;
    }
    return find_it->second;
}

rocksdb::Status MyRocks::create_db_by_existed_cf(const std::vector<std::string> &exists_cfs, bool read_only) {
    //create exsit column handlers
    vector<rocksdb::ColumnFamilyDescriptor> column_families;
    for (auto const it : exists_cfs) {
        column_families.push_back(rocksdb::ColumnFamilyDescriptor(
                it, m_column_family_options));
    }
    vector<rocksdb::ColumnFamilyHandle *> vhandles;
    rocksdb::Status ret;

    if (read_only) {
        ret = rocksdb::DB::OpenForReadOnly(m_options, m_path, column_families, &vhandles, &m_db);
    } else {
        ret = rocksdb::DB::Open(m_options, m_path, column_families, &vhandles, &m_db);
    }

    if (!ret.ok()) {
        cout << "open " << m_path << " failed ! error code:" << ret.code() << ". " << ret.ToString() << endl;
        return ret;
    }

    for (int i = 0; i < vhandles.size(); ++i) {
        m_map_handles[exists_cfs[i]] = vhandles[i];
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::create_cf(const string &cf_name) {

    if (!(m_map_handles.find(cf_name) == m_map_handles.end())) {
        return rocksdb::Status::OK();
    }
    rocksdb::ColumnFamilyHandle *cf;
    rocksdb::Status ret = m_db->CreateColumnFamily(m_column_family_options, cf_name, &cf);
    if (!ret.ok())
        return ret;
    //add to handlers map
    m_map_handles.insert({cf_name, cf});

    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::write(const string &cf_name,
                             const rocksdb::Slice &key,
                             const rocksdb::Slice &value) {
    auto cf_ptr = exist_column_family(cf_name);
    if (cf_ptr == nullptr) {
        return default_write(key, value);
    }
    rocksdb::Status s = m_db->Put(m_write_options, cf_ptr, key, value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::write(shared_ptr<rocksdb::Transaction> transaction,
                             const string &cf_name, const rocksdb::Slice &key,
                             const rocksdb::Slice &value) {
    auto cf_ptr = exist_column_family(cf_name);
    if (cf_ptr == nullptr) {
        return default_write(key, value);
    }
    rocksdb::Status s = transaction->Put(cf_ptr, key, value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::default_write(const rocksdb::Slice &key,
                                     const rocksdb::Slice &value) {
    rocksdb::Status s = m_db->Put(m_write_options, key,
                                  value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::default_write(shared_ptr<rocksdb::Transaction> transaction, const rocksdb::Slice &key,
                                     const rocksdb::Slice &value) {
    rocksdb::Status s = transaction->Put(key, value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}


rocksdb::Status MyRocks::add_put_batch(rocksdb::WriteBatch &batch,
                                     const string &cf_name,
                                     const rocksdb::Slice &key,
                                     const rocksdb::Slice &value) {
    auto cf_ptr = exist_column_family(cf_name);

    if (cf_ptr == nullptr) {
        return rocksdb::Status::IOError();
    }
    rocksdb::Status s = batch.Put(cf_ptr, key,
                                  value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::add_default_put_batch(rocksdb::WriteBatch &batch,
                                             const rocksdb::Slice &key,
                                             const rocksdb::Slice &value) {
    rocksdb::Status s = batch.Put(key,
                                  value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::add_merge_batch(rocksdb::WriteBatch &batch,
                                       const string &cf_name,
                                       const rocksdb::Slice &key,
                                       const rocksdb::Slice &value) {
    auto cf_ptr = exist_column_family(cf_name);

    if (cf_ptr == nullptr) {
        return rocksdb::Status::IOError();
    }
    rocksdb::Status s = batch.Merge(cf_ptr, key,
                                    value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::add_default_merge_batch(rocksdb::WriteBatch &batch,
                                               const rocksdb::Slice &key,
                                               const rocksdb::Slice &value) {
    rocksdb::Status s = batch.Merge(key,
                                    value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::add_delete_batch(rocksdb::WriteBatch &batch,
                                        const string &cf_name,
                                        const rocksdb::Slice &key) {
    auto cf_ptr = exist_column_family(cf_name);

    if (cf_ptr == nullptr) {
        return rocksdb::Status::IOError();
    }
    rocksdb::Status s = batch.Delete(cf_ptr, key);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::add_default_delete_batch(rocksdb::WriteBatch &batch,
                                                const rocksdb::Slice &key) {

    rocksdb::Status s = batch.Delete(key);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::merge(const string &cf_name,
                             const rocksdb::Slice &key,
                             const rocksdb::Slice &value) {
    auto cf_ptr = exist_column_family(cf_name);
    if (cf_ptr == nullptr) {
        return default_write(key, value);
    }
    rocksdb::Status s = m_db->Merge(m_write_options, cf_ptr, key, value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::merge(shared_ptr<rocksdb::Transaction> transaction,
                             const string &cf_name,
                             const rocksdb::Slice &key,
                             const rocksdb::Slice &value) {
    auto cf_ptr = exist_column_family(cf_name);
    if (cf_ptr == nullptr) {
        return default_write(key, value);
    }
    rocksdb::Status s = transaction->Merge(cf_ptr, key, value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::write_batch(rocksdb::WriteBatch &batch){
    return m_db->Write(m_write_options, &batch);
}

rocksdb::Status MyRocks::read(const string &cf_name, const rocksdb::Slice &key, string &out_value) {
    auto cf_ptr = exist_column_family(cf_name);

    if (cf_ptr == nullptr) {
        return default_read(key, out_value);
    }
    rocksdb::Status s = m_db->Get(m_read_options, cf_ptr, key, &out_value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::default_read(const rocksdb::Slice &key, string &out_value) {
    rocksdb::Status s = m_db->Get(m_read_options, key, &out_value);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

vector<rocksdb::Status> MyRocks::multi_read(const string &cf_name,
                                          const vector<rocksdb::Slice> &keys,
                                          vector<string> &out_value) {
    vector<rocksdb::Status> ret;
    auto cf_ptr = exist_column_family(cf_name);

    if (cf_ptr == nullptr) {
        return ret;
    }

    std::vector<rocksdb::ColumnFamilyHandle *> cfs;
    for (auto &val : keys) {
        cfs.emplace_back(cf_ptr);
    }

    std::vector<rocksdb::Status> ret_status = m_db->MultiGet(m_read_options,
                                                             cfs,
                                                             keys,
                                                             &out_value);
    for (auto &status : ret_status) {
        if (status.ok()) {
            ret.emplace_back(rocksdb::Status::OK());
        } else {
            ret.emplace_back(status);
        }
    }

    return ret;
}


rocksdb::Iterator *MyRocks::new_iterator(const string &cf_name) {
    auto find_handle = exist_column_family(cf_name);
    if (find_handle != nullptr) {
        return m_db->NewIterator(m_read_options, find_handle);
    }
    return m_db->NewIterator(m_read_options);
}

rocksdb::Iterator *MyRocks::new_default_iterator() {
    return m_db->NewIterator(m_read_options);
}

rocksdb::Status MyRocks::delete_key(const string &cf_name, const rocksdb::Slice &key) {
    auto cf_ptr = exist_column_family(cf_name);

    if (cf_ptr == nullptr) {
        return default_delete_key(key);
    }
    //不能使用SingleDelete, SingleDelete在Put多个版本的时候只会删除最后一个版本
    // https://rocksdb.org.cn/doc/Single-Delete.html
    //rocksdb::Status s = m_db->SingleDelete(m_write_options, cf_ptr, key);
    rocksdb::Status s = m_db->Delete(m_write_options, cf_ptr, key);
    if (s.ok()) {
        return rocksdb::Status::OK();
    }
    return s;
}

rocksdb::Status MyRocks::delete_key(shared_ptr<rocksdb::Transaction> transaction,
                                  const string &cf_name,
                                  const rocksdb::Slice &key) {
    auto cf_ptr = exist_column_family(cf_name);

    if (cf_ptr == nullptr) {
        return default_delete_key(key);
    }
    //不能使用SingleDelete, SingleDelete在Put多个版本的时候只会删除最后一个版本
    // https://rocksdb.org.cn/doc/Single-Delete.html
    //rocksdb::Status s = transaction->SingleDelete(cf_ptr, key);
    rocksdb::Status s = transaction->Delete(cf_ptr, key);
    if (s.ok()) {
        return rocksdb::Status::OK();
    }
    return s;
}

rocksdb::Status MyRocks::default_delete_key(const rocksdb::Slice &key) {
    Status status = m_db->Delete(m_write_options, key);
    if (status.ok()) {
        return rocksdb::Status::OK();
    }
    return status;
}

rocksdb::Status MyRocks::default_delete_key(shared_ptr<rocksdb::Transaction> transaction,
                                          const rocksdb::Slice &key) {
    Status status = transaction->Delete(key);
    if (status.ok()) {
        return rocksdb::Status::OK();
    }

    return status;
}

rocksdb::Status MyRocks::delete_range(const string &cf_name,
                                    const rocksdb::Slice  &begin_id,
                                    const rocksdb::Slice  &end_id) {
    auto cf_ptr = exist_column_family(cf_name);

    if (cf_ptr == nullptr) {
        return rocksdb::Status::IOError();
    }
    rocksdb::Status s = m_db->DeleteRange(m_write_options, cf_ptr, begin_id, end_id);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::default_delete_range(const rocksdb::Slice &begin_id,
                             const rocksdb::Slice &end_id){
    auto cf_ptr = exist_column_family("default");

    if (cf_ptr == nullptr) {
        return rocksdb::Status::IOError();
    }
    rocksdb::Status s = m_db->DeleteRange(m_write_options,cf_ptr, begin_id, end_id);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}

void MyRocks::flush() {
    for (auto it : m_map_handles) {
        rocksdb::FlushOptions fOptions;
        m_db->Flush(fOptions, it.second);
        m_db->CompactRange(CompactRangeOptions(), it.second, nullptr, nullptr);
    }
}

#include <rocksdb/utilities/backupable_db.h>

rocksdb::Status MyRocks::back_up(const string backup_path) {
    rocksdb::BackupEngine *backup_engine;

    auto s = BackupEngine::Open(Env::Default(), BackupableDBOptions(backup_path), &backup_engine);
    backup_engine->CreateNewBackup(m_db);

    std::vector<BackupInfo> backup_info;
    backup_engine->GetBackupInfo(&backup_info);

    for (auto &info : backup_info) {
        auto vs = backup_engine->VerifyBackup(info.backup_id);
        if (!vs.ok()) {
            return vs;
        }
    }
    return rocksdb::Status::OK();
}

rocksdb::Status MyRocks::restore(const string restore_path) {
    BackupEngineReadOnly *backup_engine;
    auto s = BackupEngineReadOnly::Open(Env::Default(), BackupableDBOptions(restore_path), &backup_engine);
    if (s.ok()) {
        backup_engine->RestoreDBFromLatestBackup(m_path, m_path);
        delete backup_engine;
        return rocksdb::Status::OK();
    }

    return s;
}


rocksdb::Status MyRocks::ingest_sstfile(const string &cf_name, const vector<string> &sst_files_path) {
    IngestExternalFileOptions ifo;
    auto cf_ptr = exist_column_family(cf_name);

    if (cf_ptr == nullptr) {
        return rocksdb::Status::IOError();
    }

    Status s = m_db->IngestExternalFile(cf_ptr, sst_files_path, ifo);
    if (!s.ok()) {
        return s;
    }
    return rocksdb::Status::OK();
}
