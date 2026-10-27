using System;
using System.IO;
using System.Text;

namespace Vrcrafter.Bootstrap
{
    internal static class ManagedLog
    {
        private static readonly object SyncRoot = new object();
        private static readonly Encoding Utf8 = new UTF8Encoding(false);

        internal static void Write(string message)
        {
            string directory = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "vrcrafter");
            string path = Path.Combine(directory, "managed.log");

            lock (SyncRoot)
            {
                Directory.CreateDirectory(directory);
                File.AppendAllText(path,
                    DateTime.UtcNow.ToString("O") + " " + message + Environment.NewLine,
                    Utf8);
            }
        }
    }
}
