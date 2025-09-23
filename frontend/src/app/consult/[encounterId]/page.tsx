"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Container,
  Typography,
  Paper,
  TextField,
  IconButton,
  Stack,
  Chip,
  Avatar,
  CircularProgress,
  Button,
  Divider,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import LocalHospitalIcon from "@mui/icons-material/LocalHospital";
import PersonIcon from "@mui/icons-material/Person";
import InfoIcon from "@mui/icons-material/Info";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import HealingIcon from "@mui/icons-material/Healing";
import MedicationIcon from "@mui/icons-material/Medication";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import DownloadIcon from "@mui/icons-material/Download";
import { useParams, useRouter } from "next/navigation";

// ========== Types ==========
export type Role = "system" | "assistant" | "user";
export type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  createdAt: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

/* ========== UI Subcomponents ========== */
function Bubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  const isAssistant = msg.role === "assistant";
  const align = isUser ? "flex-end" : "flex-start";
  const bg =
    msg.role === "user"
      ? "primary.main"
      : msg.role === "assistant"
      ? "background.paper"
      : "grey.200";
  const color = msg.role === "user" ? "primary.contrastText" : "text.primary";
  const icon = isUser ? (
    <PersonIcon />
  ) : isAssistant ? (
    <LocalHospitalIcon />
  ) : (
    <InfoIcon />
  );

  return (
    <Stack direction="row" justifyContent={align} sx={{ my: 1 }}>
      {!isUser && (
        <Avatar
          sx={{ mr: 1, bgcolor: isAssistant ? "success.main" : "grey.500" }}
        >
          {icon}
        </Avatar>
      )}
      <Paper
        elevation={isAssistant ? 1 : 0}
        sx={{
          px: 2,
          py: 1.25,
          maxWidth: "75%",
          bgcolor: bg,
          color,
          borderRadius: 3,
        }}
      >
        <Typography
          variant="body1"
          sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}
        >
          {msg.content}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {new Date(msg.createdAt).toLocaleString()}
        </Typography>
      </Paper>
      {isUser && (
        <Avatar sx={{ ml: 1, bgcolor: "primary.main" }}>
          <PersonIcon />
        </Avatar>
      )}
    </Stack>
  );
}

function ChatWindow({
  messages,
  isStreaming,
}: {
  messages: ChatMessage[];
  isStreaming: boolean;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    ref.current?.scrollTo({
      top: ref.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, isStreaming]);

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        height: "58vh",
        overflowY: "auto",
        borderRadius: 3,
        bgcolor: "background.default",
      }}
      ref={ref}
    >
      {messages.length === 0 ? (
        <Typography color="text.secondary">
          メッセージはまだありません。
        </Typography>
      ) : (
        messages.map((m) => <Bubble key={m.id} msg={m} />)
      )}
      {isStreaming && (
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1 }}>
          <CircularProgress size={18} />
          <Typography variant="body2" color="text.secondary">
            回答生成中…
          </Typography>
        </Stack>
      )}
    </Paper>
  );
}

function MessageInput({
  value,
  setValue,
  disabled,
  onSend,
}: {
  value: string;
  setValue: (v: string) => void;
  disabled: boolean;
  onSend: () => void;
}) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };
  return (
    <Paper
      variant="outlined"
      sx={{ p: 1, borderRadius: 3, display: "flex", alignItems: "center" }}
    >
      <TextField
        variant="standard"
        placeholder="症状や気になることを入力…（Enterで送信 / Shift+Enterで改行）"
        fullWidth
        multiline
        maxRows={6}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        InputProps={{ disableUnderline: true, sx: { px: 1, py: 1 } }}
      />
      <IconButton
        color="primary"
        onClick={onSend}
        disabled={disabled || !value.trim()}
      >
        <SendIcon />
      </IconButton>
    </Paper>
  );
}

function EncounterHeader({
  encounterId,
  chiefComplaint,
}: {
  encounterId: string;
  chiefComplaint?: string;
}) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        borderRadius: 3,
        display: "flex",
        flexWrap: "wrap",
        gap: 2,
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center">
        <LocalHospitalIcon />
        <Typography variant="subtitle1">診察ID: {encounterId}</Typography>
      </Stack>
      {chiefComplaint && (
        <Stack direction="row" spacing={1} alignItems="center">
          <WarningAmberIcon fontSize="small" />
          <Typography variant="body2">主訴: {chiefComplaint}</Typography>
        </Stack>
      )}
    </Paper>
  );
}

function QuickReplies({
  onPick,
  onChip,
}: {
  onPick: (text: string) => void;
  onChip: (k: "history" | "allergy" | "meds") => void;
}) {
  const replies = useMemo(
    () => [
      "胸が痛いです",
      "頭痛がひどいです",
      "息苦しさがあります",
      "発熱が続いています",
      "吐き気があります",
    ],
    []
  );
  return (
    <Stack spacing={1}>
      <Typography variant="body2" color="text.secondary">
        よくある訴え
      </Typography>
      <Stack direction="row" spacing={1} flexWrap="wrap">
        {replies.map((r) => (
          <Button
            key={r}
            size="small"
            variant="outlined"
            onClick={() => onPick(r)}
          >
            {r}
          </Button>
        ))}
      </Stack>
      <Divider sx={{ my: 1 }} />
      <Typography variant="body2" color="text.secondary">
        補助情報
      </Typography>
      <Stack direction="row" spacing={1} flexWrap="wrap">
        <Chip
          icon={<HealingIcon />}
          label="既往歴を入力"
          variant="outlined"
          onClick={() => onChip("history")}
        />
        <Chip
          icon={<MedicationIcon />}
          label="アレルギーを入力"
          variant="outlined"
          onClick={() => onChip("allergy")}
        />
        <Chip
          icon={<MedicationIcon />}
          label="服薬中の薬を入力"
          variant="outlined"
          onClick={() => onChip("meds")}
        />
      </Stack>
    </Stack>
  );
}

// ========== Helper: download markdown ==========
function downloadMarkdown(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/* ========== Page ========== */
export default function ConsultByIdPage() {
  const { encounterId } = useParams<{ encounterId: string }>();
  const router = useRouter();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [chiefComplaint, setChiefComplaint] = useState<string | undefined>();

  // clinical note states
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteMD, setNoteMD] = useState<string>("");
  const [noteLoading, setNoteLoading] = useState(false);

  const sseRef = useRef<EventSource | null>(null);
  const assistantBufferRef = useRef<string>("");

  // 初手メッセージ
  useEffect(() => {
    if (!encounterId) return;
    let aborted = false;
    async function boot() {
      try {
        const res = await fetch(`${API_BASE}/api/templates/first-message`);
        let content = "本日はどうなさいましたか？";
        if (res.ok) {
          const data = await res.json();
          content = data?.content || content;
        }
        if (!aborted) {
          setMessages([
            {
              id: `sys-${Date.now()}`,
              role: "system",
              content:
                "※ このサービスは医療行為の代替ではありません。緊急時は119番または最寄りの医療機関へ。",
              createdAt: new Date().toISOString(),
            },
            {
              id: `asst-${Date.now() + 1}`,
              role: "assistant",
              content,
              createdAt: new Date().toISOString(),
            },
          ]);
        }
      } catch {
        setMessages([
          {
            id: `sys-${Date.now()}`,
            role: "system",
            content:
              "※ このサービスは医療行為の代替ではありません。緊急時は119番または最寄りの医療機関へ。",
            createdAt: new Date().toISOString(),
          },
          {
            id: `asst-${Date.now() + 1}`,
            role: "assistant",
            content: "本日はどうなさいましたか？",
            createdAt: new Date().toISOString(),
          },
        ]);
      }
    }
    boot();
    return () => {
      aborted = true;
      sseRef.current?.close();
      sseRef.current = null;
    };
  }, [encounterId]);

  // SSE を開く
  const openSSE = useCallback(() => {
    if (!encounterId) return;
    sseRef.current?.close();
    sseRef.current = null;

    const url = `${API_BASE}/api/encounters/${encodeURIComponent(
      String(encounterId)
    )}/stream`;
    const es = new EventSource(url);
    sseRef.current = es;
    setIsStreaming(true);
    assistantBufferRef.current = "";

    const tempId = `asst-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: tempId,
        role: "assistant",
        content: "",
        createdAt: new Date().toISOString(),
      },
    ]);

    es.addEventListener("token", (e) => {
      const data = (e as MessageEvent).data;
      try {
        const parsed = JSON.parse(data as string);
        const delta = parsed.delta ?? "";
        assistantBufferRef.current += String(delta);
      } catch {
        assistantBufferRef.current += String(data || "");
      }
      setMessages((prev) =>
        prev.map((m) =>
          m.id === tempId ? { ...m, content: assistantBufferRef.current } : m
        )
      );
    });

    es.addEventListener("done", () => {
      setIsStreaming(false);
      es.close();
      sseRef.current = null;
    });

    es.onerror = () => {
      setIsStreaming(false);
      es.close();
      sseRef.current = null;
    };
  }, [encounterId]);

  // 送信
  const sendMessage = useCallback(
    async (text?: string) => {
      const id = String(encounterId || "");
      if (!id) return router.push("/");
      const content = (text ?? input).trim();
      if (!content) return;

      setIsSending(true);
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");

      try {
        const res = await fetch(
          `${API_BASE}/api/encounters/${encodeURIComponent(id)}/messages`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role: "user", content }),
          }
        );
        if (!res.ok) throw new Error(`POST messages failed: ${res.status}`);
        openSSE();
      } catch (e) {
        console.error(e);
      } finally {
        setIsSending(false);
      }
    },
    [API_BASE, encounterId, input, openSSE, router]
  );

  // クイックリプライ/補助
  const handlePickQuick = useCallback((text: string) => setInput(text), []);
  const handleChip = useCallback((kind: "history" | "allergy" | "meds") => {
    const templates = {
      history: "既往歴：",
      allergy: "アレルギー：",
      meds: "服薬中の薬：",
    } as const;
    setInput((v) => `${v ? v + "\n" : ""}${templates[kind]}`);
  }, []);

  // === 診察終了 → カルテ生成 ===
  const generateClinicalNote = useCallback(async () => {
    if (!encounterId) return;
    setNoteLoading(true);
    try {
      // バックエンドで LLM によりカルテを生成して返す想定
      // 期待レスポンス: { note_md: string, chief_complaint?: string }
      const res = await fetch(
        `${API_BASE}/api/encounters/${encodeURIComponent(
          String(encounterId)
        )}/clinical-note`,
        {
          method: "POST",
        }
      );
      if (!res.ok) throw new Error(`generate note failed: ${res.status}`);
      const data = await res.json();
      setNoteMD(String(data?.note_md || ""));
      if (data?.chief_complaint)
        setChiefComplaint(String(data.chief_complaint));
      setNoteOpen(true);
    } catch (e) {
      console.error("臨床カルテ生成エラー:", e);
      // フォールバック: その場で最低限のテンプレを作る
      const fallback =
        `# 内科カルテ\n\n` +
        `**主訴**: ${chiefComplaint ?? "（未入力）"}\n\n` +
        `**現病歴**: （チャット内容をもとに要約）\n\n` +
        `**既往歴**: \n\n` +
        `**アレルギー**: \n\n` +
        `**内服薬**: \n\n` +
        `**身体所見**: \n\n` +
        `**鑑別診断**: \n\n` +
        `**評価**: \n\n` +
        `**Plan**: 検査/処方/指導/フォローアップ\n\n` +
        `---\n作成時刻: ${new Date().toLocaleString()}`;
      setNoteMD(fallback);
      setNoteOpen(true);
    } finally {
      setNoteLoading(false);
    }
  }, [API_BASE, chiefComplaint, encounterId]);

  const handleEndConsult = useCallback(async () => {
    try {
      await fetch(
        `${API_BASE}/api/encounters/${encodeURIComponent(
          String(encounterId)
        )}/end`,
        { method: "POST" }
      );
      // 終了後にカルテ生成
      await generateClinicalNote();
    } catch (e) {
      console.error("診察終了APIエラー:", e);
      await generateClinicalNote(); // 終了API失敗時もカルテだけは見せる
    }
  }, [API_BASE, encounterId, generateClinicalNote]);

  // クリップボードへコピー
  const copyNote = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(noteMD);
    } catch (e) {
      console.error("コピー失敗", e);
    }
  }, [noteMD]);

  // Markdown を保存
  const saveNote = useCallback(() => {
    const filename = `clinical_note_${encounterId}_${new Date()
      .toISOString()
      .slice(0, 10)}.md`;
    downloadMarkdown(filename, noteMD);
  }, [encounterId, noteMD]);

  if (!encounterId) {
    return (
      <Container sx={{ py: 6 }}>
        <Typography variant="h5" gutterBottom>
          encounterId が指定されていません
        </Typography>
      </Container>
    );
  }

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Container component="main" sx={{ py: 3, flex: 1, maxWidth: "md" }}>
        <Stack spacing={2}>
          <Stack direction="row" spacing={1} alignItems="center">
            <LocalHospitalIcon />
            <Typography variant="h5">AIドクター 診察</Typography>
            <Tooltip title="対話は学習の参考として保存されます。緊急時は119番へ。">
              <InfoIcon fontSize="small" color="disabled" />
            </Tooltip>
          </Stack>

          <EncounterHeader
            encounterId={String(encounterId)}
            chiefComplaint={chiefComplaint}
          />

          <ChatWindow messages={messages} isStreaming={isStreaming} />

          <QuickReplies onPick={handlePickQuick} onChip={handleChip} />

          <MessageInput
            value={input}
            setValue={setInput}
            disabled={isSending || isStreaming}
            onSend={() => sendMessage()}
          />

          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            justifyContent="flex-end"
          >
            <AccessTimeIcon fontSize="small" color="disabled" />
            <Typography variant="caption" color="text.secondary">
              Enterで送信 / Shift+Enterで改行
            </Typography>
          </Stack>

          {/* === 診察終了ボタン === */}
          <Divider sx={{ my: 2 }} />
          <Stack direction="row" justifyContent="flex-end" gap={1}>
            <Button
              variant="contained"
              color="error"
              onClick={handleEndConsult}
              startIcon={<LocalHospitalIcon />}
            >
              診察終了（カルテ生成）
            </Button>
          </Stack>
        </Stack>
      </Container>

      {/* === カルテプレビュー Dialog === */}
      <Dialog
        open={noteOpen}
        onClose={() => setNoteOpen(false)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>内科カルテ（プレビュー）</DialogTitle>
        <DialogContent dividers>
          {noteLoading ? (
            <Stack direction="row" spacing={1} alignItems="center">
              <CircularProgress size={20} />
              <Typography variant="body2">カルテを生成しています…</Typography>
            </Stack>
          ) : (
            <Typography
              component="pre"
              sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}
            >
              {noteMD}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={copyNote} startIcon={<ContentCopyIcon />}>
            コピー
          </Button>
          <Button onClick={saveNote} startIcon={<DownloadIcon />}>
            Markdown保存
          </Button>
          <Button
            onClick={() => {
              setNoteOpen(false);
              router.push("/");
            }}
            variant="contained"
          >
            終了してホームへ
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
