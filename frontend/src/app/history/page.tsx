"use client";

import { useMemo } from "react";
import useSWR from "swr";
import {
  Box,
  Container,
  Typography,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Chip,
  Stack,
  Avatar,
  Divider,
  Tooltip,
  IconButton,
  CircularProgress,
  Button,
} from "@mui/material";
import LocalHospitalIcon from "@mui/icons-material/LocalHospital";
import ArrowForwardIosIcon from "@mui/icons-material/ArrowForwardIos";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import RefreshIcon from "@mui/icons-material/Refresh";
import HistoryIcon from "@mui/icons-material/History";
import FlagIcon from "@mui/icons-material/Flag";
import { useRouter } from "next/navigation";

type Triage = "green" | "yellow" | "red" | undefined;
type EncounterStatus = "active" | "closed";

type Encounter = {
  id: string;
  userId?: string;
  chiefComplaint?: string | null;
  status: EncounterStatus;
  startedAt: string; // ISO
  endedAt?: string | null;
  triageLevel?: Triage;
  needsAttention?: boolean; // 任意（なければ triage=red を優先）
};

const fetcher = (url: string) =>
  fetch(url).then((r) => {
    if (!r.ok) throw new Error(`Fetch failed: ${r.status}`);
    return r.json();
  });

function formatDateTime(iso?: string | null) {
  if (!iso) return "-";
  const d = new Date(iso);
  // 日本語・JST表示
  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

function StatusChip({ status }: { status: EncounterStatus }) {
  const color = status === "active" ? "success" : "default";
  const label = status === "active" ? "進行中" : "終了";
  return <Chip size="small" color={color} variant="outlined" label={label} />;
}

function TriageChip({ triage }: { triage?: Triage }) {
  if (!triage) return <Chip size="small" label="未評価" variant="outlined" />;
  const map: Record<
    Exclude<Triage, undefined>,
    { label: string; color: "success" | "warning" | "error" }
  > = {
    green: { label: "低", color: "success" },
    yellow: { label: "中", color: "warning" },
    red: { label: "高", color: "error" },
  };
  const { label, color } = map[triage];
  return <Chip size="small" color={color} label={`緊急度:${label}`} />;
}

export default function HistoryPage() {
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
  const router = useRouter();

  const { data, error, isLoading, mutate } = useSWR<Encounter[]>(
    `${API_BASE}/api/encounters`,
    fetcher,
    { revalidateOnFocus: true }
  );

  const encounters = useMemo(() => data ?? [], [data]);

  const handleOpen = (id: string) => {
    router.push(`/consult/${encodeURIComponent(id)}`);
  };

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Container component="main" sx={{ py: 4, flex: 1 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
          <HistoryIcon fontSize="large" />
          <Typography variant="h4">診察履歴</Typography>
          <Box sx={{ flexGrow: 1 }} />
          <Tooltip title="再読み込み">
            <span>
              <IconButton onClick={() => mutate()} disabled={isLoading}>
                {isLoading ? <CircularProgress size={20} /> : <RefreshIcon />}
              </IconButton>
            </span>
          </Tooltip>
        </Stack>

        <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
          自分の診察セッション一覧です。行をクリックすると該当の診察画面（読み専/継続）に移動します。
        </Typography>

        {error && (
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
            <ErrorOutlineIcon color="error" />
            <Typography color="error">読み込みに失敗しました。</Typography>
            <Button size="small" onClick={() => mutate()}>
              再試行
            </Button>
          </Stack>
        )}

        {isLoading ? (
          <Stack alignItems="center" sx={{ py: 8 }}>
            <CircularProgress />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              読み込み中…
            </Typography>
          </Stack>
        ) : encounters.length === 0 ? (
          <Box
            sx={{
              border: "1px dashed",
              borderColor: "divider",
              borderRadius: 2,
              p: 4,
              textAlign: "center",
            }}
          >
            <Typography variant="h6" sx={{ mb: 1 }}>
              診察履歴はありません
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              ホーム画面から「診察を開始する」で新しい診察を作成できます。
            </Typography>
            <Button
              variant="contained"
              startIcon={<LocalHospitalIcon />}
              href="/"
            >
              ホームへ
            </Button>
          </Box>
        ) : (
          <List
            sx={{
              width: "100%",
              bgcolor: "background.paper",
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 2,
              overflow: "hidden",
            }}
          >
            {encounters.map((e, idx) => {
              const primary = e.chiefComplaint?.trim() || "主訴未入力";
              const started = formatDateTime(e.startedAt);
              const ended = e.endedAt ? formatDateTime(e.endedAt) : undefined;
              const showFlag = e.needsAttention || e.triageLevel === "red";
              return (
                <Box key={e.id}>
                  <ListItemButton onClick={() => handleOpen(e.id)}>
                    <ListItemIcon sx={{ minWidth: 44 }}>
                      <Avatar sx={{ width: 32, height: 32 }} alt="enc">
                        <LocalHospitalIcon fontSize="small" />
                      </Avatar>
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Stack
                          direction={{ xs: "column", sm: "row" }}
                          spacing={1}
                          alignItems={{ xs: "flex-start", sm: "center" }}
                        >
                          <Typography variant="subtitle1">{primary}</Typography>
                          <Stack direction="row" spacing={1}>
                            <StatusChip status={e.status} />
                            <TriageChip triage={e.triageLevel} />
                            {showFlag && (
                              <Chip
                                size="small"
                                color="error"
                                icon={<FlagIcon />}
                                label="要フラグ"
                                variant="outlined"
                              />
                            )}
                          </Stack>
                        </Stack>
                      }
                      secondary={
                        <Typography variant="body2" color="text.secondary">
                          開始: {started}
                          {ended ? `　/　終了: ${ended}` : ""}
                        </Typography>
                      }
                    />
                    <ArrowForwardIosIcon fontSize="small" color="disabled" />
                  </ListItemButton>
                  {idx !== encounters.length - 1 && <Divider />}
                </Box>
              );
            })}
          </List>
        )}
      </Container>
    </Box>
  );
}
