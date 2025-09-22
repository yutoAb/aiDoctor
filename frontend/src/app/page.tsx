"use client";

import AddTodoForm from "@/components/AddTodoForm";
import {
  Typography,
  Box,
  Container,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Checkbox,
  Button,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import { fetcher } from "../../hooks/fetcher";
import useSWR from "swr";

type Todo = { id: number; title: string };

export default function Home() {
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

  const {
    data: todos,
    error,
    isLoading,
    mutate,
  } = useSWR<Todo[]>(`${API_BASE}/api/todos`, fetcher);

  const handleDelete = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/todos/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Delete failed");

      await mutate();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <Box sx={{ pb: 8 /* フッター分の余白を確保 */ }}>
      <Container component="main" sx={{ py: 4 }}>
        <Typography variant={"h2"}>Todos</Typography>
        {todos && todos.length === 0 ? (
          <Typography variant="h6" color="text.secondary">
            タスクはありません．
          </Typography>
        ) : (
          <List>
            {todos &&
              todos.map((t) => (
                <ListItem key={t.id} className="text-base">
                  <ListItemIcon>
                    <Checkbox edge="start" tabIndex={-1} disableRipple />
                  </ListItemIcon>
                  <ListItemText primary={t.title} />
                  <Button
                    variant="outlined"
                    startIcon={<DeleteIcon />}
                    onClick={() => handleDelete(t.id)}
                  >
                    削除
                  </Button>
                </ListItem>
              ))}
          </List>
        )}
        <AddTodoForm />
      </Container>

      {/* footer 部分 */}
      <Box
        component="footer"
        sx={{
          position: "fixed",
          bottom: 0,
          left: 0,
          width: "100%",
          display: "flex",
          gap: 3,
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "center",
          py: 2,
          bgcolor: "background.paper",
          boxShadow: 3,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          フッター
        </Typography>
      </Box>
    </Box>
  );
}