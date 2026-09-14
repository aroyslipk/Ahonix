import React, { createContext, useContext } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

const WorkspaceContext = createContext(null);

export function WorkspaceProvider({ children }) {
  const { data } = useQuery({
    queryKey: ["workspaces"],
    queryFn: async () => (await api.get("/workspaces")).data,
  });

  const active = data?.workspaces?.find((w) => w.workspace_id === data.active_workspace_id) || data?.workspaces?.[0];

  return (
    <WorkspaceContext.Provider
      value={{
        workspace: active,
        workspaces: data?.workspaces || [],
        currency: active?.currency || "USD",
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export const useWorkspace = () => useContext(WorkspaceContext) || { currency: "USD" };
