"use client";

import { useState, useCallback } from "react";
import {
  Typography,
  Box,
  Container,
  Button,
  Stack,
  Card,
  CardContent,
  CircularProgress,
  Link as MUILink,
} from "@mui/material";
import LocalHospitalIcon from "@mui/icons-material/LocalHospital";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import HistoryIcon from "@mui/icons-material/History";
import SettingsIcon from "@mui/icons-material/Settings";
import { useRouter } from "next/navigation";
import NextLink from "next/link";

export default function Home() {
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
  const router = useRouter();
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartConsultation = useCallback(async () => {
    setError(null);
    setIsStarting(true);
    try {
      // 要件: /consult/new に POST
      const res = await fetch(`${API_BASE}/consult/new`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}), // ここで chief_complaint など渡してもOK
      });

      if (!res.ok) {
        throw new Error(`Failed to start consultation: ${res.status}`);
      }

      // 期待レスポンス例: { encounter_id: "enc_xxx" }
      const data = await res.json();
      const encounterId: string =
        data.encounter_id || data.id || data.encounterId;

      if (!encounterId) {
        throw new Error("encounter_id がレスポンスに含まれていません。");
      }

      router.push(`/consult/${encodeURIComponent(encounterId)}`);
    } catch (e: any) {
      console.error(e);
      setError(e?.message ?? "診察開始に失敗しました。");
      setIsStarting(false);
    }
  }, [API_BASE, router]);

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Container component="main" sx={{ py: 8, flex: 1 }}>
        <Stack alignItems="center" spacing={4}>
          <Stack direction="row" spacing={1} alignItems="center">
            <LocalHospitalIcon fontSize="large" />
            <Typography variant="h3" component="h1">
              AI ドクター
            </Typography>
          </Stack>

          <Typography variant="h6" color="text.secondary" align="center">
            チャット形式で症状をお伺いし、受診の目安や次の行動をサポートします。
            緊急時は必ず救急要請や最寄りの医療機関をご利用ください。
          </Typography>

          <Card sx={{ maxWidth: 720, width: "100%" }}>
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                診察の流れ
              </Typography>
              <Typography variant="body2" color="text.secondary">
                1. 「診察を開始する」を押すとセッションが作成されます。
                <br />
                2. 医師テンプレートの初手メッセージが表示され、チャットが始まります。
                <br />
                3. 会話は履歴に保存され、後から見返せます。
              </Typography>
            </CardContent>
          </Card>

          <Stack direction="row" spacing={2}>
            <Button
              size="large"
              variant="contained"
              startIcon={
                isStarting ? <CircularProgress size={20} /> : <PlayArrowIcon />
              }
              onClick={handleStartConsultation}
              disabled={isStarting}
            >
              {isStarting ? "診察を開始中…" : "診察を開始する"}
            </Button>

            <Button
              size="large"
              variant="outlined"
              component={NextLink}
              href="/history"
              startIcon={<HistoryIcon />}
            >
              履歴を見る
            </Button>

            <Button
              size="large"
              variant="outlined"
              component={NextLink}
              href="/settings"
              startIcon={<SettingsIcon />}
            >
              設定
            </Button>
          </Stack>

          {error && (
            <Typography color="error" variant="body2">
              {error}
            </Typography>
          )}

          <Box>
            <Typography variant="body2" color="text.secondary" align="center">
              実装メモ：チャット画面では{" "}
              <code>{"<EncounterHeader />"}</code>
              、<code>{"<ChatWindow />"}</code>、<code>{"<MessageInput />"}</code>
              、<code>{"<TypingIndicator />"}</code>、<code>{"<QuickReplies />"}</code>
              を組み合わせ、SSE/WSでストリーミング表示を行います。
            </Typography>
          </Box>
        </Stack>
      </Container>

      <Box
        component="footer"
        sx={{
          position: "sticky",
          bottom: 0,
          width: "100%",
          borderTop: 1,
          borderColor: "divider",
          bgcolor: "background.paper",
          py: 2,
        }}
      >
        <Container>
          <Typography variant="body2" color="text.secondary" align="center">
            ※ このサービスは医療行為の代替ではありません。緊急性が高い症状（激しい胸痛、
            呼吸困難、意識障害 など）はすぐに119番通報や医療機関を受診してください。
            {" "}
            <MUILink component={NextLink} href="/terms">
              利用規約
            </MUILink>{" "}
            |{" "}
            <MUILink component={NextLink} href="/privacy">
              プライバシー
            </MUILink>
          </Typography>
        </Container>
      </Box>
    </Box>
  );
}
