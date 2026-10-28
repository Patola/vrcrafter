using System;
using System.Reflection;

namespace Vrcrafter.Bootstrap
{
    public static class BootstrapState
    {
        public static int RunAfterResolver()
        {
            try
            {
                if (!GameIdentity.Validate())
                {
                    return 4;
                }

                foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
                {
                    ManagedLog.Write("ASSEMBLY " + assembly.FullName);
                }

                HarmonyBootstrap.Install();

                int ping = NativeBridge.Ping(41);
                ManagedLog.Write("PING=" + ping);
                return ping == 42 ? 0 : 3;
            }
            catch (Exception ex)
            {
                try
                {
                    ManagedLog.Write("EXCEPTION " + ex);
                }
                catch (Exception)
                {
                }
                return 2;
            }
        }
    }
}
