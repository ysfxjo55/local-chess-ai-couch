import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useConversationsList() {
  return useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.listConversations(),
  });
}

export function useConversationMessages(id: number | null) {
  return useQuery({
    queryKey: ["conversation", id],
    queryFn: () => api.getConversationMessages(id!),
    enabled: id !== null,
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteConversation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
