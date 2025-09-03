#include <iconv.h>
#include <cerrno>
#include <cstring>
#include <string>
#include <vector>
#include <cctype>

// すでに提示した convert_encoding がある前提（なければ同名で実装してください）
static std::string convert_encoding(const std::string& in, const char* from, const char* to);

// ざっくり UTF-8 妥当性チェック（簡易版）
static bool is_valid_utf8(const std::string& s) {
    const unsigned char* p = reinterpret_cast<const unsigned char*>(s.data());
    size_t i = 0, n = s.size();
    while (i < n) {
        unsigned char c = p[i];
        if (c <= 0x7F) { i++; continue; } // ASCII
        size_t need = 0;
        if ((c & 0xE0) == 0xC0) need = 1;
        else if ((c & 0xF0) == 0xE0) need = 2;
        else if ((c & 0xF8) == 0xF0) need = 3;
        else return false;
        if (i + need >= n) return false;
        for (size_t k = 1; k <= need; ++k)
            if ((p[i+k] & 0xC0) != 0x80) return false;
        // 先頭バイトの最短形式チェックは簡略化（必要なら追加）
        i += need + 1;
    }
    return true;
}

// 先頭の UTF-8/UTF-16 BOM を除去
static std::string strip_bom(const std::string& s) {
    if (s.size() >= 3 &&
        (unsigned char)s[0] == 0xEF &&
        (unsigned char)s[1] == 0xBB &&
        (unsigned char)s[2] == 0xBF) {
        return s.substr(3);
    }
    if (s.size() >= 2) {
        unsigned char b0 = (unsigned char)s[0], b1 = (unsigned char)s[1];
        // UTF-16LE BOM FF FE / UTF-16BE BOM FE FF
        if ((b0 == 0xFF && b1 == 0xFE) || (b0 == 0xFE && b1 == 0xFF))
            return s.substr(2);
    }
    return s;
}

// 前後の空白/制御文字をトリム
static std::string trim(const std::string& s) {
    size_t b = 0, e = s.size();
    auto issp = [](unsigned char c){ return std::isspace(c) || c == '\0'; };
    while (b < e && issp((unsigned char)s[b])) b++;
    while (e > b && issp((unsigned char)s[e-1])) e--;
    return s.substr(b, e - b);
}

// Excel 等から来た文字列を UTF-8 に統一
static std::string ensure_utf8_from_excel(const std::string& raw) {
    std::string s = strip_bom(trim(raw));
    if (s.empty()) return s;

    // まず UTF-8 として妥当ならそのまま採用
    if (is_valid_utf8(s)) return s;

    // UTF-16LE/BE の可能性（NULが多い等）を簡易判定して試す
    // 直接判定せず両方試してもOK
    {
        std::string u8 = convert_encoding(s, "UTF-16LE", "UTF-8");
        if (!u8.empty() && is_valid_utf8(u8)) return u8;
        u8 = convert_encoding(s, "UTF-16BE", "UTF-8");
        if (!u8.empty() && is_valid_utf8(u8)) return u8;
    }

    // 日本語 Windows 系・他候補から UTF-8 へ
    const char* cands[] = {"CP932", "SHIFT_JIS", "EUC-JP"};
    for (auto enc : cands) {
        std::string u8 = convert_encoding(s, enc, "UTF-8");
        if (!u8.empty() && is_valid_utf8(u8)) return u8;
    }

    // どうしても決まらなければ元を返す（最終手段）
    return s;
}
