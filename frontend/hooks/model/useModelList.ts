import { useQuery } from "@tanstack/react-query";
import { modelService } from "@/services/modelService";

export function useModelList(tenantId: string | null) {
  return useQuery({
    queryKey: ["models", tenantId],
    queryFn: () => modelService.getAllModels(),
    enabled: !!tenantId,
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
    refetchOnMount: 'always', // Always refetch when component mounts (e.g., when switching tabs)
  });
}
