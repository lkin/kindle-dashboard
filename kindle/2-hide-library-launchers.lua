-- Hide shell-script launchers from the book library without moving the files.
-- Remove this patch and restart KOReader to show them again.
local FileChooser = require("ui/widget/filechooser")
local original = FileChooser.show_file

function FileChooser:show_file(filename, fullpath)
    if self.name == "filemanager" and type(fullpath) == "string"
        and fullpath:sub(1, 18) == "/mnt/us/documents/"
        and type(filename) == "string" and filename:lower():match("%.sh$") then
        return false
    end
    return original(self, filename, fullpath)
end
