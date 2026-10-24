import { createContext, useContext } from "react";

export type User = { sub: string; role: string; region: string; caps: string[]; mfa?: boolean } | null;
export const Ctx = createContext<{ user: User; setUser: (u: User) => void; reload: () => void }>({ user: null, setUser: () => {}, reload: () => {} });
export const useUser = () => useContext(Ctx).user;
