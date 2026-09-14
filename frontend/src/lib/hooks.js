import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useSection(key, path, enabled = true) {
  return useQuery({
    queryKey: [key],
    enabled,
    queryFn: async () => {
      const { data } = await api.get(path);
      return data;
    },
  });
}
