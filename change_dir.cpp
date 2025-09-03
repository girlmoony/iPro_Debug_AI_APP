#include <sys/types.h>
#include <sys/stat.h>
#include <dirent.h>
#include <fcntl.h>
#include <unistd.h>
#include <iconv.h>

#include <cerrno>
#include <cstring>
#include <string>
#include <vector>
#include <iostream>

static std::string convert_encoding(const std::string& in, const char* from, const char* to) {
    iconv_t cd = iconv_open(to, from);
    if (cd == (iconv_t)-1) return std::string();

    std::string out;
    out.resize(in.size() * 4 + 16);
    char* inbuf = const_cast<char*>(in.data());
    size_t inbytes = in.size();
    char* outbuf = out.data();
    size_t outbytes = out.size();

    while (inbytes > 0) {
        size_t r = iconv(cd, &inbuf, &inbytes, &outbuf, &outbytes);
        if (r == (size_t)-1) {
            if (errno == E2BIG) {
                size_t used = out.size() - outbytes;
                out.resize(out.size() * 2);
                outbuf = out.data() + used;
                outbytes = out.size() - used;
                continue;
            } else {
                iconv_close(cd);
                return std::string();
            }
        }
    }
    iconv_close(cd);
    out.resize(out.size() - outbytes);
    return out;
}

static void split_parent_leaf(const std::string& path, std::string& parent, std::string& leaf) {
    auto pos = path.find_last_of('/');
    if (pos == std::string::npos) { parent = "."; leaf = path; }
    else {
        parent = (pos == 0) ? "/" : path.substr(0, pos);
        leaf = path.substr(pos + 1);
    }
}

// parent（ASCIIのみが望ましい）の直下から、target_utf8 と「見た目一致」する実バイト名を探す
static bool resolve_raw_leaf(const std::string& parent, const std::string& target_utf8, std::string& raw_leaf_out) {
    const char* encs[] = {"UTF-8", "CP932", "SHIFT_JIS", "EUC-JP"};

    DIR* dp = opendir(parent.c_str());
    if (!dp) return false;

    bool found = false;
    while (dirent* de = readdir(dp)) {
        if (std::strcmp(de->d_name, ".") == 0 || std::strcmp(de->d_name, "..") == 0) continue;
        std::string raw = de->d_name;

        // 1) raw(未知のエンコ) → UTF-8 に変換して一致するか
        for (auto enc : encs) {
            std::string as_utf8 = convert_encoding(raw, enc, "UTF-8");
            if (!as_utf8.empty() && as_utf8 == target_utf8) {
                raw_leaf_out = raw;
                found = true;
                break;
            }
        }
        if (found) break;

        // 2) target_utf8(UTF-8) → 各エンコに変換したバイト列と raw が一致するか
        for (auto enc : encs) {
            std::string as_enc = convert_encoding(target_utf8, "UTF-8", enc);
            if (!as_enc.empty() && as_enc == raw) {
                raw_leaf_out = raw;
                found = true;
                break;
            }
        }
        if (found) break;
    }
    closedir(dp);
    return found;
}

// 与えられた path を、必要なら上記解決を通して opendir する
static DIR* opendir_portable(const std::string& path_utf8) {
    // まずは素直にトライ（環境がUTF-8で合っていればこれで開ける）
    DIR* dp = opendir(path_utf8.c_str());
    if (dp) return dp;

    // ダメなら親を開いて末端名を解決
    std::string parent, leaf_utf8;
    split_parent_leaf(path_utf8, parent, leaf_utf8);

    std::string raw_leaf;
    if (!resolve_raw_leaf(parent, leaf_utf8, raw_leaf)) {
        // どうしても解決できない場合は元のエラーのまま返す
        return nullptr;
    }

    std::string full_raw = (parent == "/") ? ("/" + raw_leaf) : (parent + "/" + raw_leaf);
    return opendir(full_raw.c_str());
}
