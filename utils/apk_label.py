# -*- coding: utf-8 -*-
"""从设备 APK 提取应用名（纯 Python 解析 Android binary XML + 资源表）

流程：adb exec-out unzip -p <apk> AndroidManifest.xml → AXML 解析找 application 的
label 属性；若 label 是资源引用，再 unzip -p resources.arsc 解析资源表取字符串。
任何一步失败返回 None（调用方回退包名）。
"""
import subprocess
import struct

# ---------------- string pool ----------------
_UTF8_FLAG = 0x00000100


def _read_u16(buf, off):
    return struct.unpack_from("<H", buf, off)[0]


def _read_u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def _utf8_len(buf, off):
    """UTF-8 变长长度前缀；返回 (长度, 新偏移)"""
    b = buf[off]
    if b & 0x80:
        b2 = buf[off + 1]
        n = ((b & 0x7F) << 8) | b2
        return n, off + 2
    return b, off + 1


def parse_string_pool(buf, off):
    """解析 ResStringPool；返回 (strs列表, 新偏移)"""
    # chunk: type(2) headerSize(2) size(4) stringCount(4) styleCount(4) flags(4) stringsStart(4) stylesStart(4)
    hs = _read_u16(buf, off + 2)
    count = _read_u32(buf, off + 8)
    flags = _read_u32(buf, off + 16)
    strs_start = _read_u32(buf, off + 20)
    chunk_size = _read_u32(buf, off + 4)
    utf8 = bool(flags & _UTF8_FLAG)
    str_off_base = off + hs
    data_base = off + strs_start
    strs = []
    for i in range(count):
        so_off = str_off_base + i * 4
        if so_off + 4 > len(buf):  # 截断容错
            break
        so = _read_u32(buf, so_off)
        p = data_base + so
        try:
            if utf8:
                # utf8: 先 u8len（char16 长度）再 utf8len
                _, p2 = _utf8_len(buf, p)
                n, p3 = _utf8_len(buf, p2)
                s = buf[p3:p3 + n].decode("utf-8", "replace")
            else:
                n = _read_u16(buf, p)
                s = buf[p + 2:p + 2 + n * 2].decode("utf-16-le", "replace")
        except Exception:
            s = ""
        strs.append(s)
    return strs, off + chunk_size


# ---------------- AXML ----------------
RES_STRING_POOL = 0x0001
RES_XML_START_ELEMENT = 0x0102
RES_XML_END_ELEMENT = 0x0103
TYPE_STRING = 0x03
TYPE_REFERENCE = 0x01


def _parse_axml(data):
    """解析 AXML，返回 (string_pool, resource_map, [元素列表])；
    每元素 (name_idx, [(name_idx, dataType, data), ...])"""
    pool, off = parse_string_pool(data, 8)
    res_map = {}
    elems = []
    while off + 8 <= len(data):
        typ = _read_u16(data, off)
        hs = _read_u16(data, off + 2)
        size = _read_u32(data, off + 4)
        if typ == 0x0180:  # resource map：属性名索引 → 资源 ID
            n = (size - hs) // 4 if size > hs else 0
            for i in range(n):
                res_map[i] = _read_u32(data, off + hs + i * 4)
        elif typ == RES_XML_START_ELEMENT:
            # ResXMLTree_node: type(2) headerSize(2) size(4) lineNumber(4) comment(4)
            # ResXMLTree_attrExt: ns(4) name(4) attrStart(2) attrSize(2) attrCount(2) id(2) class(2) style(2)
            ns = _read_u32(data, off + 16)
            name = _read_u32(data, off + 20)
            attr_start = _read_u16(data, off + 24)
            attr_size = _read_u16(data, off + 26)
            attr_count = _read_u16(data, off + 28)
            # attributeStart 相对 attrExt（元素偏移+16）的偏移
            attr_base = off + 16 + attr_start
            if attr_size == 0:
                attr_size = 20
            attrs = []
            for i in range(attr_count):
                a = attr_base + i * attr_size
                if a + 19 >= len(data):
                    break
                a_ns = _read_u32(data, a)
                a_name = _read_u32(data, a + 4)
                a_raw = _read_u32(data, a + 8)
                # Res_value: size(2) res0(1) dataType(1) data(4)
                dtype = data[a + 15]
                ddata = _read_u32(data, a + 16)
                attrs.append((a_ns, a_name, a_raw, dtype, ddata))
            elems.append((ns, name, attrs))
        off += size if size > 0 else 8
    return pool, res_map, elems


def _attr_name(pool, res_map, idx):
    """属性名：优先字符串池；否则经 resource map 转资源 ID（0x01010447=android:label）"""
    s = _pool_str(pool, idx)
    if s:
        return s
    rid = res_map.get(idx)
    return rid if rid is not None else ""


def _pool_str(pool, idx):
    try:
        return pool[idx]
    except Exception:
        return ""


# ---------------- ARSC（label 资源引用） ----------------
RES_TABLE_PACKAGE = 0x0200
RES_TABLE_TYPE = 0x0201


def _parse_arsc_label(data, res_id):
    """解析 resources.arsc（允许截断），返回资源 ID 对应字符串（若为 TYPE_STRING）"""
    try:
        pool, off = parse_string_pool(data, 12)  # ResTable_header 12 字节后是 string pool
    except Exception:
        return None
    # 找 package chunk
    while off + 8 <= len(data):
        typ = _read_u16(data, off)
        hs = _read_u16(data, off + 2)
        size = _read_u32(data, off + 4)
        if typ == RES_TABLE_PACKAGE:
            # headerSize=284(0x011C)：packageId(4) name(256) typeStrings(4) lastPublicType(4) keyStrings(4) lastPublicKey(4) typeIdOffset(4)
            if hs < 284:
                off += size
                continue
            pkg_off = off
            key_strings_off = pkg_off + 8 + 4 + 256 + 8  # typeStrings 后是 keyStrings 偏移
            key_off = pkg_off + _read_u32(data, key_strings_off)
            keys, _ = parse_string_pool(data, key_off)
            type_id_offset = _read_u32(data, pkg_off + 284) if hs >= 288 else 0

            def _resolve(rid, _seen):
                """按资源 ID 查 entry，返回 (vtype, vdata) 或 None"""
                if rid in _seen:
                    return None
                _seen.add(rid)
                res_tt = (rid >> 16) & 0xFF
                res_ee = rid & 0xFFFF
                tt = pkg_off + hs
                while tt + 8 <= pkg_off + size and tt + 8 <= len(data):
                    ttyp = _read_u16(data, tt)
                    tsize = _read_u32(data, tt + 4)
                    if tsize <= 0:
                        break
                    if ttyp == RES_TABLE_TYPE and tsize >= 56:
                        tid = data[tt + 8]
                        entry_count = _read_u32(data, tt + 12)
                        if tid + type_id_offset == res_tt and res_ee < entry_count:
                            entries_start = _read_u32(data, tt + 16)
                            type_hs = _read_u16(data, tt + 2)
                            eo_off = tt + type_hs + res_ee * 4
                            if eo_off + 4 <= len(data):
                                eo = _read_u32(data, eo_off)
                                e_abs = tt + entries_start + eo
                                if eo != 0xFFFFFFFF and e_abs + 16 <= len(data):
                                    eflags = _read_u16(data, e_abs + 2)
                                    if not (eflags & 0x0001):  # 非 COMPLEX
                                        vt = data[e_abs + 11]
                                        vd = _read_u32(data, e_abs + 12)
                                        return (vt, vd)
                    tt += tsize
                return None

            # 解析引用链（最多 6 层防环）
            cur = res_id
            for _ in range(6):
                rv = _resolve(cur, set())
                if rv is None:
                    return None
                vt, vd = rv
                if vt == TYPE_STRING:
                    return _pool_str(pool, vd)
                if vt == TYPE_REFERENCE:
                    cur = vd
                    continue
                return None
            return None
        off += size
    return None


# ---------------- zip 内条目流式读取（dd + 本地 zlib） ----------------
def _dd(adb_path, apk, bs, skip, count):
    r = subprocess.run([adb_path, "exec-out",
                        "dd if=%s bs=%d skip=%d count=%d 2>/dev/null" % (apk, bs, skip, count)],
                       capture_output=True, timeout=60)
    return r.stdout


def _zip_entry_info(adb_path, apk, entry_name):
    """返回 zip 条目 (method, csize, local_header_off) 或 None"""
    try:
        r = subprocess.run([adb_path, "shell", "stat", "-c", "%s", apk],
                           capture_output=True, text=True, timeout=10,
                           encoding="utf-8", errors="replace")
        apk_size = int((r.stdout or "0").strip().split()[0])
    except Exception:
        return None
    bs = 65536
    tail = _dd(adb_path, apk, bs, apk_size // bs, 1)
    if len(tail) < 22:
        return None
    i = tail.rfind(b"PK\x05\x06")
    if i < 0 or i + 22 > len(tail):
        return None
    cd_size = struct.unpack_from("<I", tail, i + 12)[0]
    cd_off = struct.unpack_from("<I", tail, i + 16)[0]
    cd_blk = cd_off // bs
    cd = _dd(adb_path, apk, bs, cd_blk, cd_size // bs + 2)
    cd_rel = cd_off - cd_blk * bs
    cd_data = cd[cd_rel:cd_rel + cd_size]
    p = 0
    while p + 46 <= len(cd_data):
        if cd_data[p:p + 4] != b"PK\x01\x02":
            break
        meth = struct.unpack_from("<H", cd_data, p + 10)[0]
        csize = struct.unpack_from("<I", cd_data, p + 20)[0]
        name_len = struct.unpack_from("<H", cd_data, p + 28)[0]
        extra_len = struct.unpack_from("<H", cd_data, p + 30)[0]
        comment_len = struct.unpack_from("<H", cd_data, p + 32)[0]
        lho = struct.unpack_from("<I", cd_data, p + 42)[0]
        name = cd_data[p + 46:p + 46 + name_len].decode("utf-8", "replace")
        if name == entry_name:
            return (meth, csize, lho)
        p += 46 + name_len + extra_len + comment_len
    return None


def _zip_entry_csize(adb_path, apk, entry_name):
    info = _zip_entry_info(adb_path, apk, entry_name)
    return info[1] if info else None


def _read_zip_entry_head(adb_path, apk, entry_name, head_limit):
    """从设备 APK 读取 zip 内条目解压后的前 head_limit 字节（无需整文件传输）"""
    try:
        r = subprocess.run([adb_path, "shell", "stat", "-c", "%s", apk],
                           capture_output=True, text=True, timeout=10,
                           encoding="utf-8", errors="replace")
        apk_size = int((r.stdout or "0").strip().split()[0])
    except Exception:
        return None
    bs = 65536
    # 1) 最后一块拿 EOCD
    tail = _dd(adb_path, apk, bs, apk_size // bs, 1)
    if len(tail) < 22:
        return None
    i = tail.rfind(b"PK\x05\x06")
    if i < 0 or i + 22 > len(tail):
        return None
    cd_size = struct.unpack_from("<I", tail, i + 12)[0]
    cd_off = struct.unpack_from("<I", tail, i + 16)[0]
    # 2) 读 CD
    cd_blk = cd_off // bs
    cd = _dd(adb_path, apk, bs, cd_blk, cd_size // bs + 2)
    cd_rel = cd_off - cd_blk * bs
    cd_data = cd[cd_rel:cd_rel + cd_size]
    # 3) 找条目
    p = 0
    target = None
    while p + 46 <= len(cd_data):
        if cd_data[p:p + 4] != b"PK\x01\x02":
            break
        meth = struct.unpack_from("<H", cd_data, p + 10)[0]
        csize = struct.unpack_from("<I", cd_data, p + 20)[0]
        name_len = struct.unpack_from("<H", cd_data, p + 28)[0]
        extra_len = struct.unpack_from("<H", cd_data, p + 30)[0]
        comment_len = struct.unpack_from("<H", cd_data, p + 32)[0]
        lho = struct.unpack_from("<I", cd_data, p + 42)[0]
        name = cd_data[p + 46:p + 46 + name_len].decode("utf-8", "replace")
        if name == entry_name:
            target = (meth, csize, lho)
            break
        p += 46 + name_len + extra_len + comment_len
    if target is None:
        return None
    meth, csize, lho = target
    # 读 local header 前缀，取 name_len/extra_len 定位数据区
    lh = _dd(adb_path, apk, bs, lho // bs, 1)
    lh_rel = lho % bs
    if len(lh) < lh_rel + 30:
        return None
    lh_nlen = struct.unpack_from("<H", lh, lh_rel + 26)[0]
    lh_xlen = struct.unpack_from("<H", lh, lh_rel + 28)[0]
    data_off = lho + 30 + lh_nlen + lh_xlen
    # 5) 读压缩数据
    blk = data_off // bs
    raw = _dd(adb_path, apk, bs, blk, (csize + data_off % bs) // bs + 2)
    start = data_off % bs
    if len(raw) < start + csize:
        return None
    raw = raw[start:start + csize]
    if meth == 0:  # STORED
        return raw[:head_limit] if head_limit else raw
    if meth == 8:  # DEFLATED
        try:
            d = zlib.decompressobj()
            if head_limit:
                return d.decompress(raw, head_limit)
            return d.decompress(raw)
        except Exception:
            return None
    return None


# ---------------- 主入口 ----------------
def fetch_label(adb_path, apk_path, timeout=45):
    """返回应用名（None=解析失败，调用方回退包名）"""
    try:
        r = subprocess.run([adb_path, "exec-out", "unzip", "-p", apk_path,
                            "AndroidManifest.xml"],
                           capture_output=True, timeout=timeout)
        if r.returncode != 0 or len(r.stdout) < 16:
            return None
        pool, res_map, elems = _parse_axml(r.stdout)
        # 找 application 元素；找不到就找第一个带 label 属性的元素
        def _an(idx):
            return _attr_name(pool, res_map, idx)
        target = None
        for ns, name, attrs in elems:
            if _pool_str(pool, name) == "application":
                target = (name, attrs)
                break
        if target is None:
            for ns, name, attrs in elems:
                if any(_an(a_name) in ("label", 0x01010447) for _, a_name, _, _, _ in attrs):
                    target = (name, attrs)
                    break
        if target is None:
            return None
        _, attrs = target
        for a_ns, a_name, a_raw, dtype, ddata in attrs:
            if _an(a_name) not in ("label", 0x01010447):
                continue
            if dtype == TYPE_STRING:
                return _pool_str(pool, ddata) or None
            if dtype == TYPE_REFERENCE:
                # 资源引用：string 类型块在 arsc 尾部（按 type id 排序），需全量解压
                if csize := _zip_entry_csize(adb_path, apk_path, "resources.arsc"):
                    if csize > 80 * 1024 * 1024:
                        return None  # 超大 arsc 跳过（回退包名）
                arsc = _read_zip_entry_head(adb_path, apk_path, "resources.arsc", 0)
                if not arsc:
                    return None
                return _parse_arsc_label(arsc, ddata)
        return None
    except Exception:
        return None
