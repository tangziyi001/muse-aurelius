# Pi 打印 Skill

经家中 Raspberry Pi 用 IPP 协议向打印机发送打印任务。用户 2026-09-26 亲立：说"打印"时直接经 Pi 发到实体打印机，不只生成 PDF。

## 打印机

- **HP LaserJet MFP M29w**（黑白激光），IP `192.168.1.220`（DHCP，变了要重扫）
- IPP: `ipp://192.168.1.220/ipp/print`（端口 631）
- 关键实测结论（2026-09-26）：
  - `document-format=application/pdf` → `0x040a` operation-not-supported（别用）
  - `document-format=application/octet-stream` → `0x0000` 成功，打印机会自己识别 PDF 内容
  - 打印机声明只支持光栅格式（PCLm/pwg-raster/urf），但 octet-stream 实测可直接喂 PDF

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
