using System.Runtime.InteropServices;

namespace Vrcrafter.Bootstrap
{
    internal static class NativeBridge
    {
        [DllImport("winhttp", EntryPoint = "VrcrafterPing")]
        internal static extern int Ping(int value);
    }
}
