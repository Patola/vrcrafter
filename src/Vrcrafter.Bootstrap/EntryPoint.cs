using System;
using System.Diagnostics;
using System.IO;

namespace Vrcrafter.Bootstrap
{
    public static class EntryPoint
    {
        public static int Start()
        {
            try
            {
                using (Process process = Process.GetCurrentProcess())
                {
                    ManagedLog.Write("START utc=" + DateTime.UtcNow.ToString("O")
                        + " pid=" + process.Id
                        + " unity-mono=" + Environment.Version
                        + " domain=" + AppDomain.CurrentDomain.FriendlyName);
                }

                string payload = Environment.GetEnvironmentVariable("VRCRAFTER_PAYLOAD");
                if (String.IsNullOrWhiteSpace(payload))
                {
                    ManagedLog.Write("EXCEPTION VRCRAFTER_PAYLOAD is unavailable");
                    return 5;
                }

                AssemblyResolver.Install(Path.Combine(payload, "managed"));
                return BootstrapState.RunAfterResolver();
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
