"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { TOKEN_KEY } from "./api";
import { AccountError, clearToken, getMe, getToken, type User } from "./accounts";

type Status = "loading" | "authed" | "guest" | "error";

type AuthState = {
  status: Status;
  user: User | null;
  errorMessage: string;
};

type AuthContextValue = AuthState & { logout: () => void };

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const userRef = useRef<User | null>(null);
  const [state, setState] = useState<AuthState>({ status: "loading", user: null, errorMessage: "" });

  const sync = useCallback(async () => {
    if (!getToken()) {
      userRef.current = null;
      setState({ status: "guest", user: null, errorMessage: "" });
      return;
    }
    if (userRef.current) return; // пользователь уже загружен

    // Чтобы после входа не мелькали кнопки гостя
    setState((s) => (s.status === "authed" ? s : { status: "loading", user: null, errorMessage: "" }));

    try {
      const user = await getMe();
      userRef.current = user;
      setState({ status: "authed", user, errorMessage: "" });
    } catch (err) {
      userRef.current = null;
      if (err instanceof AccountError && err.status === 401) {
        setState({ status: "guest", user: null, errorMessage: "" }); // токен уже удалён
      } else {
        // сервер недоступен: токен не трогаем, но подтвердить вход не можем
        setState({
          status: "error",
          user: null,
          errorMessage: err instanceof Error ? err.message : "Не удалось проверить вход.",
        });
      }
    }
  }, []);

  // Проверяем вход при загрузке и при каждой навигации (так подхватывается вход со страницы /login)
  useEffect(() => {
    void sync();
  }, [pathname, sync]);

  // Вход или выход в другой вкладке
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === TOKEN_KEY || e.key === null) {
        userRef.current = null;
        void sync();
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [sync]);

  const logout = useCallback(() => {
    clearToken();
    userRef.current = null;
    setState({ status: "guest", user: null, errorMessage: "" });
    router.push("/");
    router.refresh();
  }, [router]);

  const value = useMemo(() => ({ ...state, logout }), [state, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth нужно вызывать внутри <AuthProvider> (см. app/layout.tsx)");
  return ctx;
}