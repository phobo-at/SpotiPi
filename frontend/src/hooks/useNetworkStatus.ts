/** @jsxImportSource preact */
import { useEffect, useState } from "preact/hooks";

type NetworkStatus = "online" | "offline";

interface UseNetworkStatusResult {
  networkStatus: NetworkStatus;
  setNetworkStatus: (status: NetworkStatus) => void;
}

export function useNetworkStatus(initialStatus: NetworkStatus = "online"): UseNetworkStatusResult {
  const [networkStatus, setNetworkStatus] = useState<NetworkStatus>(initialStatus);

  useEffect(() => {
    const onOnline = () => setNetworkStatus("online");
    const onOffline = () => setNetworkStatus("offline");
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  return {
    networkStatus,
    setNetworkStatus
  };
}
