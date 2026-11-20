# 备份与恢复

## 只有一样东西需要备份

```
<AstrBot>\data\
```

里面有：

| 文件 / 目录 | 内容 | 丢了会怎样 |
|---|---|---|
| `data_v4.db` | 会话、人格、聊天记录、平台统计 | 她「忘记」所有对话 |
| `plugin_data/` | 插件数据，**含长期记忆向量库** | 长期记忆全丢 |
| `cmd_config.json` | 全部配置 | 需要重配模型/平台/白名单 |
| `plugins/` | 已安装插件 | 需要重装 |
| `personas/` 等 | 人格与附件 | 人格丢失 |

> 其余部分（AstrBot 源码、NapCat、ffmpeg、安装包）都能重新获取，不必备份。

## 备份（服务器上双击）

`scripts/backup-data.bat` 会把 `data` 目录打包到桌面：

```bat
backup-data.bat
→ 生成 %USERPROFILE%\Desktop\dafeiyu-data-YYYYMMDD-HHMMSS.zip
```

然后通过远程桌面的磁盘重定向把 zip 拖回本机保存。

## 手动备份（不装脚本时）

在服务器上：

```powershell
$src = 'C:\大肥鱼\AstrBot\data'
$out = "$env:USERPROFILE\Desktop\dafeiyu-data-$(Get-Date -Format yyyyMMdd-HHmmss).zip"
Compress-Archive -Path $src -DestinationPath $out -CompressionLevel Optimal
```

> **不要在 AstrBot 运行时直接复制 `data_v4.db`**：SQLite 在写入中复制可能得到损坏的库。要么先停 AstrBot 再复制，要么用上面的打包（压缩过程也建议先停服务）。
>
> 判断是否停干净：`data_v4.db` 旁的 `-wal` / `-shm` 文件消失，说明写入已落盘。

## 恢复

1. 停 AstrBot（结束所有 `python.exe`）
2. 备份现有 `data`（改名成 `data.bak-日期`）
3. 解压备份 zip，把里面的 `data` 放回原位
4. 启动 AstrBot，打开 6185 确认配置与记忆都在

## 备份策略建议

| 频率 | 保留 |
|---|---|
| 每周一次 | 最近 4 份 |
| 改动配置/装插件前后各一次 | 最近 2 份 |

数据量参考：一套完整 `data`（含记忆与表情包索引）通常在几十 MB 量级，一次打包一分钟内。

## 不要放进 Git

即使是私有仓库也不要提交：

- `data_v4.db*`（聊天记录）
- `plugin_data/`（长期记忆、可能的用户画像）
- `cmd_config.json` 的明文版本（含 key）
- 任何 `*.txt` 凭据文件、Cookie、Token
- 备份 zip
