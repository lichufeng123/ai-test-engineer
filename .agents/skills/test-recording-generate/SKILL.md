---
name: test-recording-generate
description: Use when synthetic test recordings must be generated for transcription, automatic tagging, silence handling, or audio upload validation without using real customer speech.
license: MIT
metadata:
  author: ai-test-engineer
  version: "1.0.0"
---

# 合成测试录音生成

用于按声明离线生成合成语音或静音测试文件，并输出可回读的音频元数据、SHA-256 与 Fixture 清单。本 Skill 只负责录音文件制作，不负责上传、打标执行、业务结论或创建账号；后者分别遵循正式测试流程及 `test-data-and-account-fixture-management`。

## 使用前

1. 读取当前任务的已审核需求/规则/用例或临时测试章程、录音入口限制、允许的格式/采样率/时长、标签语义及下游转写/AI 分析链路。缺少口径时可生成 `pending` 探索样本，但不得编造正式预期。
2. 冻结本轮目的、场景矩阵、唯一 Fixture ID、预期来源、独立 Oracle、证据与清理范围。明确标记已确认事实、推断与待确认问题；不能仅用录音文本或生成器的 `expected_tags` 判定系统通过。
3. 只使用虚构的合成文本，不包含真实客户/员工姓名、号码、声音、私人地址或内部机密。不要上传真实录音，也不要把实测敏感音频提交至仓库。若需要转写与语义可听性证明，生成后人工试听/独立转写复核，并记录具体文件哈希和结果；仅有可播放/时长校验不证明说了预期的话。
4. 上传产品、调用接口、写入业务环境、清理已有数据前另行完成测试计划、环境与写入授权；生产、批量、真实通知等高风险动作另行确认。纯本地生成不会操作业务系统。

## 依赖与边界

- 使用仓库自带 `scripts/generate_recordings.py`（Python 3.9+ 标准库）；语音需要 macOS `say` 中已安装的合成音色，音频编码/校验需要 `ffmpeg` 与 `ffprobe`。没有所需工具时显式阻塞，不会联网下载、替换语音服务或改用真实录音。静音只需要 ffmpeg/ffprobe。
- 输入格式和示例见 `assets/recording-spec.example.json`。一次运行选定统一输出格式 `wav`、`mp3` 或 `m4a`，16 kHz 单声道；WAV 为 PCM 16 bit。合成音色、操作系统和工具版本可能改变音色与哈希，不能跨机器承诺比特级可复现；用 Fixture ID、输入 spec 哈希、输出文件哈希记录本次运行。
- 三种 `kind`：`speech` 单人朗读；`dialogue` 多人轮流对话（`turns` 逐轮声明 `speaker`、`text` 和可选 `voice`，轮次间插入 `pause_seconds` 停顿）；`silence` 生成指定时长的静音，用于区分无内容与处理失败。
- `speech` 和 `dialogue` 都不保证精确时长。需要贴近真实业务长度时用 `min_duration_seconds` / `max_duration_seconds` 阻断过短或过长的样本；长度不足即整次运行失败且不交付任何文件。`silence` 接受 0.1–60 秒时长。语速 120–240 WPM。
- 同一 fixture 文本相同会生成字节相同的文件（便于构造“同一录音重复处理”样本）；反之不同音色/工具版本会改变哈希，不能把哈希差异解释为业务差异。
- 方言、语速与情绪变化、真实背景噪声、精确时间轴、断续/削波、多人抢话、TTS 发音自然度、ASR 质量与真实设备麦克风特性均不支持，不得暗示已覆盖。对话只是轮流朗读，不是真实对话录制，用于验证链路与语义，不用于评估音质或说话人分离。
- `expectation_status: pending` 不得附 `expected_tags`；清单中的 `turns` 保留逐轮文本与音色，便于独立转写核对；`approved` 必须同时声明 `oracle_reference` 和 `expected_tags`，仅为追踪人工声明，清单中的 `expectations_verified` 固定为 `false`，不是对业务来源的自动鉴权。

## 运行

在项目根目录执行（将示例复制并改为当前任务自己的合成文本和稳定 ID）：

```bash
python3 .agents/skills/test-recording-generate/scripts/generate_recordings.py \
  --spec .agents/skills/test-recording-generate/assets/recording-spec.example.json \
  --output "$TMPDIR/recording-run-001"
```

输出目录必须不存在；已有目录不会覆盖。生成时会对语音和对话执行可听性检查（`volumedetect` 平均音量低于 -60 dB 即视为合成失败），并把 `mean_volume_db` 写回清单；静音样本不参与该检查。成功后必须整包交付三样东西，缺一不可：音频、`recording_manifest.json`（机器字段与哈希）、`recording_transcripts.md`（逐字稿文档，逐段列出文件名、说话人、音色、时长和完整台词）。逐字稿文档由生成器固定产出，不得只把文本留在 spec JSON 或聊天里；它是人工复核和后续转写比对的依据。交付时逐份核对哈希、编码、时长，并试听或独立转写确认合成内容。失败时不交付部分目录，修正输入/工具后用新的运行目录重试。把本次 spec、音频和校验回执置于受控的运行目录并按本任务工作项登记；默认不把生成的音频或包含业务内容的文本提交公共仓库。环境中没有 `$TMPDIR` 时自行选择受控的新目录。

## 自动打标签场景设计

以已审核标签/记忆口径为依据，分别准备正例、无标签反例、易混表达与静音。每条使用不同 `fixture_id`，记录文本/预期来源和音频哈希。

逐字稿文档是这条链路的交付物，不是附带说明：上传后的转写结果、标签与记忆都应与它逐段比对，并把差异记录到对应 fixture。

覆盖多命中与去重时，除单维正例外至少准备：一条同时命中多个维度的录音（逐维度分别核对新增结果）、同一条录音的重复处理、以及同义不同措辞的另一条录音（核对语义重复是否被抑制）。同时逐维度核对单条录音内的重复表述只产生一条记忆，不因复述次数增加条数。语音是否清晰以及转写是否准确需要独立验证；若转写失败，不应把下游未打标直接判定为标签逻辑缺陷。真实执行时逐条冻结上传目标、断言、独立 Oracle、操作边界和停止条件；上传后结合录音身份、转写、AI 状态与标签结果逐级排查，不以脚本成功或两个同源页面一致代替证明。
