using System;
using System.Diagnostics;
using System.Reflection;

namespace Vrcrafter.Bootstrap
{
    public static class EntryPoint
    {
        public static int Start()
        {
            try
            {
                ManagedLog.Write("START utc=" + DateTime.UtcNow.ToString("O")
                    + " pid=" + Process.GetCurrentProcess().Id
                    + " unity-mono=" + Environment.Version
                    + " domain=" + AppDomain.CurrentDomain.FriendlyName);

                foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
                {
                    ManagedLog.Write("ASSEMBLY " + assembly.FullName);
                }

                int ping = NativeBridge.Ping(41);
                ManagedLog.Write("PING=" + ping);
                return ping == 42 ? 0 : 3;
            }
            catch (Exception ex)
            {
                ManagedLog.Write("EXCEPTION " + ex);
                return 2;
            }
        }
    }
}
