# -*- coding: utf-8 -*-
"""
简历元数据水印清理工具
=====================
在线简历工具（如"小林简历"）导出 PDF 时，会把品牌名写进文件的元数据 Title。
浏览器打开 PDF 时会把该标题显示在标签页 / 阅读器标题栏，看起来就像"水印文字"。

本工具：
  1. 拖入（或选择）PDF 文件
  2. 自动检测元数据中的简历品牌水印
  3. 按用户输入的新标题重写元数据，清除导出工具痕迹
  4. 页面内容零改动，另存为  <原文件名>_无水印.pdf

用法：
  双击运行         → 图形界面
  --selftest <pdf> → 命令行自检（供打包验证）
  --input <pdf> --title <标题> → 命令行静默处理
"""
import os
import re
import sys
import threading

import pymupdf

# 常见在线简历工具的品牌关键词（大小写不敏感）
BRAND_KEYWORDS = [
    "小林简历", "超级简历", "wondercv", "五百丁", "锤子简历",
    "在线简历制作", "简历模板", "一键导出", "免费简历", "职徒",
    "知页", "简历本", "稻壳", "canva", "resumeway", "五百丁",
]


def detect_brand(meta: dict, xml: str = "") -> list:
    """返回 [(字段名, 原值, 命中关键词), ...]"""
    hits, seen = [], set()
    for field in ("title", "author", "subject", "keywords", "creator", "producer"):
        val = meta.get(field) or ""
        for kw in BRAND_KEYWORDS:
            if kw.lower() in val.lower():
                key = (field, val)
                if key not in seen:
                    seen.add(key)
                    hits.append((field, val, kw))
                break
    for kw in BRAND_KEYWORDS:
        if kw.lower() in xml.lower():
            hits.append(("XMP元数据", "", kw))
            break
    return hits


def clean_pdf(src: str, new_title: str, new_author: str = "",
              scrub_tools: bool = True) -> tuple:
    """清理单个 PDF，返回 (输出路径, 是否成功, 检测到的水印列表, 说明)"""
    doc = pymupdf.open(src)
    try:
        if doc.needs_pass and not doc.authenticate(""):
            raise ValueError("文件已加密，无法处理")

        old = doc.metadata
        old_title = old.get("title", "")
        xml = ""
        try:
            xml = doc.get_xml_metadata() or ""
        except Exception:
            pass
        hits = detect_brand(old, xml)

        def keep(field):
            """无品牌痕迹的字段保留原值，有痕迹的清空"""
            v = old.get(field, "") or ""
            return "" if any(kw.lower() in v.lower() for kw in BRAND_KEYWORDS) else v

        doc.set_metadata({
            "title": new_title,
            "author": new_author or (keep("author")),
            "subject": keep("subject"),
            "keywords": keep("keywords"),
            "creator": "" if scrub_tools else keep("creator"),
            "producer": "" if scrub_tools else keep("producer"),
        })

        # XMP 元数据（部分浏览器优先读取它）
        if xml:
            new_xml = xml
            if old_title and old_title in new_xml:
                new_xml = new_xml.replace(old_title, new_title)
            for kw in BRAND_KEYWORDS:
                if kw.lower() in new_xml.lower():
                    new_xml = re.sub(re.escape(kw), new_title, new_xml, flags=re.I)
            if new_xml != xml:
                try:
                    doc.set_xml_metadata(new_xml)
                except Exception:
                    pass

        base, ext = os.path.splitext(src)
        dst = f"{base}_无水印{ext}"
        doc.save(dst, garbage=4, deflate=True)
    finally:
        doc.close()

    # 回读验证
    chk = pymupdf.open(dst)
    ok = (chk.metadata.get("title") == new_title)
    n_pages = chk.page_count
    chk.close()
    note = f"共 {n_pages} 页，内容未改动" + ("" if hits else "（未检测到品牌水印，仅更新了标题）")
    return dst, ok, hits, note


# ---------------------------------------------------------------- CLI / 自检
def run_cli() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argv = sys.argv[1:]
    if "--selftest" in argv:
        i = argv.index("--selftest")
        pdf = argv[i + 1] if i + 1 < len(argv) else ""
        if not pdf or not os.path.isfile(pdf):
            print("selftest: no file"); return 2
        dst, ok, hits, note = clean_pdf(pdf, "自检测试标题", "自检")
        print(f"selftest: ok={ok} out={dst} hits={len(hits)} {note}")
        if ok and os.path.isfile(dst):
            os.remove(dst)
            return 0
        return 1
    if "--input" in argv:
        pdf = argv[argv.index("--input") + 1]
        title = argv[argv.index("--title") + 1] if "--title" in argv else \
            os.path.splitext(os.path.basename(pdf))[0]
        dst, ok, hits, note = clean_pdf(pdf, title)
        print(("OK  " if ok else "FAIL") + " -> " + dst)
        return 0 if ok else 1
    return 2


# ---------------------------------------------------------------- GUI
def run_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox

    dnd_ok = False
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
        root = TkinterDnD.Tk()
        dnd_ok = True
    except Exception:
        root = tk.Tk()

    root.title("简历水印清理工具")
    root.geometry("620x560")
    root.minsize(560, 500)
    root.configure(bg="#f4f6fa")

    state = {"files": []}

    # ---- 顶部拖放区 ----
    drop = tk.Frame(root, bg="#e8eefc", highlightthickness=2,
                    highlightbackground="#9db8e8", cursor="hand2")
    drop.pack(fill="x", padx=24, pady=(22, 10), ipady=34)
    drop_lbl = tk.Label(drop, text="将 PDF 拖到这里，或点击选择文件",
                        bg="#e8eefc", fg="#34508c",
                        font=("Microsoft YaHei UI", 13, "bold"))
    drop_lbl.pack()
    file_lbl = tk.Label(drop, text="", bg="#e8eefc", fg="#5a6b8c",
                        font=("Microsoft YaHei UI", 9), wraplength=520)
    file_lbl.pack(pady=(6, 0))

    def set_files(paths):
        state["files"] = list(paths)
        names = "\n".join(os.path.basename(p) for p in paths)
        file_lbl.config(text=names if len(names) < 400 else names[:400] + " …")
        if paths:
            # 默认标题 = 第一个文件的文件名（不含扩展名）
            title_var.set(os.path.splitext(os.path.basename(paths[0]))[0])
            detect_and_show(paths[0])
        btn_run.config(state="normal" if paths else "disabled")

    def detect_and_show(path):
        try:
            doc = pymupdf.open(path)
            if doc.needs_pass and not doc.authenticate(""):
                det_var.set("⚠ 文件已加密，无法处理")
                doc.close(); return
            xml = ""
            try:
                xml = doc.get_xml_metadata() or ""
            except Exception:
                pass
            hits = detect_brand(doc.metadata, xml)
            old_title = doc.metadata.get("title", "") or "（空）"
            doc.close()
            if hits:
                det_var.set(f"检测到品牌水印：{old_title}")
                det_var_color = "#b3261e"
                det_lbl.config(fg=det_var_color)
            else:
                det_var.set("未检测到品牌水印（仍可按下方输入更新标题）")
                det_lbl.config(fg="#1b7f4d")
        except Exception as e:
            det_var.set(f"读取失败：{e}")
            det_lbl.config(fg="#b3261e")

    def pick_files(_event=None):
        paths = filedialog.askopenfilenames(
            title="选择 PDF 文件", filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")])
        if paths:
            set_files(paths)

    drop.bind("<Button-1>", pick_files)
    drop_lbl.bind("<Button-1>", pick_files)
    if dnd_ok:
        drop.drop_target_register(DND_FILES)
        drop.dnd_bind("<<Drop>>", lambda e: set_files(root.tk.splitlist(e.data)))

    # ---- 检测结果 ----
    det_var = tk.StringVar(value="等待放入文件…")
    det_lbl = tk.Label(root, textvariable=det_var, bg="#f4f6fa", fg="#5a6b8c",
                       font=("Microsoft YaHei UI", 10), wraplength=560, justify="left")
    det_lbl.pack(anchor="w", padx=26)

    # ---- 设置区 ----
    form = tk.Frame(root, bg="#f4f6fa")
    form.pack(fill="x", padx=26, pady=(14, 4))

    tk.Label(form, text="新标题", bg="#f4f6fa", fg="#222",
             font=("Microsoft YaHei UI", 10, "bold"), width=12, anchor="w").grid(row=0, column=0, sticky="w", pady=6)
    title_var = tk.StringVar()
    title_entry = tk.Entry(form, textvariable=title_var, font=("Microsoft YaHei UI", 11),
                           relief="solid", bd=1)
    title_entry.grid(row=0, column=1, sticky="ew", pady=6, ipady=5)

    tk.Label(form, text="作者（可选）", bg="#f4f6fa", fg="#222",
             font=("Microsoft YaHei UI", 10, "bold"), width=12, anchor="w").grid(row=1, column=0, sticky="w", pady=6)
    author_var = tk.StringVar()
    author_entry = tk.Entry(form, textvariable=author_var, font=("Microsoft YaHei UI", 11),
                            relief="solid", bd=1)
    author_entry.grid(row=1, column=1, sticky="ew", pady=6, ipady=5)

    scrub_var = tk.BooleanVar(value=True)
    tk.Checkbutton(form, text="同时清除导出工具痕迹（Creator / Producer）",
                   variable=scrub_var, bg="#f4f6fa", font=("Microsoft YaHei UI", 9),
                   anchor="w").grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
    form.columnconfigure(1, weight=1)

    # ---- 状态 & 按钮 ----
    status_var = tk.StringVar(value="")
    status_lbl = tk.Label(root, textvariable=status_var, bg="#f4f6fa", fg="#333",
                          font=("Microsoft YaHei UI", 10), wraplength=560, justify="left")
    status_lbl.pack(anchor="w", padx=26, pady=(8, 0))

    btn_run = tk.Button(root, text="开始处理", state="disabled",
                        font=("Microsoft YaHei UI", 11, "bold"), bg="#2f6fed", fg="white",
                        activebackground="#2559c4", activeforeground="white",
                        relief="flat", padx=30, pady=6, cursor="hand2")
    btn_run.pack(pady=(12, 6))

    def do_run():
        if not state["files"]:
            return
        new_title = title_var.get().strip()
        if not new_title:
            messagebox.showwarning("提示", "请先填写新标题", parent=root)
            return
        btn_run.config(state="disabled")
        status_var.set("处理中…")

        def worker():
            lines = []
            for p in state["files"]:
                try:
                    dst, ok, hits, note = clean_pdf(p, new_title, author_var.get().strip(),
                                                    scrub_var.get())
                    mark = "✓" if ok else "✗"
                    lines.append(f"{mark} {os.path.basename(p)} → {dst}\n    {note}")
                except Exception as e:
                    lines.append(f"✗ {os.path.basename(p)}：{e}")
            def done():
                status_var.set("\n".join(lines))
                if dnd_ok:
                    pass
                btn_run.config(state="normal")
            root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    btn_run.config(command=do_run)

    tk.Label(root, text="处理原则：只改文件属性（元数据），页面内容保持原样；\n"
                        "结果另存为 <原文件名>_无水印.pdf，不覆盖原文件。",
             bg="#f4f6fa", fg="#8a94a6", font=("Microsoft YaHei UI", 9),
             justify="left").pack(side="bottom", anchor="w", padx=26, pady=(0, 12))

    if not dnd_ok:
        det_var.set("（当前环境不支持拖拽，请点击上方区域选择文件）")

    root.mainloop()


def main():
    argv = sys.argv[1:]
    if "--selftest" in argv or "--input" in argv:
        sys.exit(run_cli())
    try:
        run_gui()
    except Exception:
        # --noconsole 打包后崩溃无处显示，写入日志便于排查
        import traceback
        log = os.path.join(os.path.expanduser("~"), "ResumeCleaner_crash.log")
        with open(log, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
