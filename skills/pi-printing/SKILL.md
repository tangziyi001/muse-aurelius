# Pi 打印 Skill

经家中 Raspberry Pi 用 IPP 协议向打印机发送打印任务。用户 2026-09-26 亲立：说"打印"时直接经 Pi 发到实体打印机，不只生成 PDF。

## 打印机

- **HP LaserJet MFP M29w**（黑白激光），IP `192.168.1.220`（DHCP，变了要重扫）
- IPP: `ipp://192.168.1.220/ipp/print`（端口 631）
- 关键实测结论（2026-09-26）：
  - `document-format=application/pdf` → `0x040a` operation-not-supported（别用）
  - `document-format=application/octet-stream` + PDF → `0x0000` 但**实际没打出**（打印机默默丢弃，不支持 PDF 解析）
  - 正确路线：`pdf_to_pwg.py` 把 PDF 转成 PWG raster（sgray_8，打印机自声明支持），再用 `document-format=image/pwg-raster` 发 Print-Job
  - PWG 头严格按 CUPS raster-stream.c 的 WRITE_PWG 逻辑：`RaS2` + cups_page_header2_t 大端序
  - 传文件用 150dpi 版（~6.5MB/3页），300dpi 的 26MB 在 Pi→打印机链路上超时
- 打印机休眠注意：HP M29w 长时间不用会掉线（ping 不通、整网段扫不到 9100），需用户先开机/唤醒并确认连上 WiFi
- ⚠️ 2026-09-27 实测：PWG raster 任务会搞死打印机网络栈——17MB 整份和 8.7MB 半份在 sendall 中途超时，随后打印机整网段消失（非 DHCP 换 IP，逐个扫过 9100），需断电重启。用户已两次观察到"一打印就掉线"。在查明 PWG 头/数据格式问题前，**不要再向该打印机发 PWG 任务**，每次尝试都要用户亲手重启。当前 pi_print.py（发原始 PDF + octet-stream）只会得到 0x0000 默默丢弃，同样不要用。两份 8.7MB PWG 暂存在 Pi 的 /config/pi-print/part1.pwg、part2.pwg（持久），修好格式后再试。

## 用法

```bash
# 1. 把 PDF 传到 Pi
scp "文件.pdf" pi_print.py pihome:/tmp/
# 2. 在 Pi 上执行打印
ssh pihome 'cd /tmp && python3 pi_print.py "文件.pdf"'
```

`pi_print.py` 返回 exit 0 且打印 `ipp-status=0x0000` 即任务被接受。
用 Get-Jobs（operation 0x000A）查队列：空队列 = 任务已处理完。

## 找打印机（IP 变了时）

```bash
ssh pihome 'for i in $(seq 1 254); do (timeout 1 bash -c "echo > /dev/tcp/192.168.1.$i/9100" 2>/dev/null && echo "printer: 192.168.1.$i") & done; wait'
```

注意：连 Pi 的 SSH 是 HA 的 SSH add-on 容器（Alpine/BusyBox），不是 Pi 本体，
但它能访问 192.168.1.x 局域网，够用。`pihome` alias 配在 `/root/.ssh/config`。
