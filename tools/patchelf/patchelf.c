#include <ctype.h>
#include "elf.h"
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

static bool is_section_in_file(const Elf32_Shdr *shdr, off_t file_size);
static bool is_string_table_in_file(const Elf32_Shdr *shdr, const char *f, off_t file_size);
static char *find_symbol_data(const char *sym, const Elf32_Ehdr *ehdr, const Elf32_Shdr *shdrs, const Elf32_Sym *symbol, char *f, off_t file_size);
// With dest NULL, only checks that source fits in size bytes and is well formed.
static bool try_patch_value(const char *sym, char *dest, const char *source, size_t size);

int main(int argc, char *argv[])
{
    int exit_code = 1;

    int fd = -1;
    char *f = MAP_FAILED;

    if (argc < 2 || argc % 2 != 0)
    {
        fprintf(stderr, "Usage: %s <filename> [<symbol> <value>]...\n", argv[0]);
        goto error;
    }

    if ((fd = open(argv[1], O_RDWR)) == -1)
    {
        fprintf(stderr, "open(%s, O_RDWR) failed: %s\n", argv[1], strerror(errno));
        goto error;
    }

    struct stat st;
    if (fstat(fd, &st) == -1)
    {
        perror("stat failed");
        goto error;
    }

    if ((f = mmap(NULL, st.st_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0)) == MAP_FAILED)
    {
        perror("mmap failed");
        goto error;
    }

    if (memcmp(f, ELFMAG, 4) != 0)
    {
        fprintf(stderr, "not an ELF file\n");
        goto error;
    }

    const Elf32_Ehdr *ehdr = (Elf32_Ehdr *)f;
    if (st.st_size < (off_t)sizeof(Elf32_Ehdr) || ehdr->e_shoff > st.st_size
     || (off_t)(ehdr->e_shnum * sizeof(Elf32_Shdr)) > st.st_size - ehdr->e_shoff)
    {
        fprintf(stderr, "section header table lies outside the file\n");
        goto error;
    }
    const Elf32_Shdr *shdrs = (Elf32_Shdr *)(f + ehdr->e_shoff);

    if (ehdr->e_shstrndx == SHN_UNDEF || ehdr->e_shstrndx >= ehdr->e_shnum)
    {
        fprintf(stderr, "no section name string table\n");
        goto error;
    }
    const Elf32_Shdr *shdr_shstr = &shdrs[ehdr->e_shstrndx];
    if (!is_string_table_in_file(shdr_shstr, f, st.st_size))
    {
        fprintf(stderr, "bad section name string table\n");
        goto error;
    }
    const char *shstr = (const char *)(f + shdr_shstr->sh_offset);
    const Elf32_Shdr *shdr_symtab = NULL;
    const Elf32_Shdr *shdr_strtab = NULL;
    for (int i = 0; i < ehdr->e_shnum; i++)
    {
        if (shdrs[i].sh_name >= shdr_shstr->sh_size) continue;
        const char *sh_name = shstr + shdrs[i].sh_name;
        if (strcmp(sh_name, ".symtab") == 0)
            shdr_symtab = &shdrs[i];
        else if (strcmp(sh_name, ".strtab") == 0)
            shdr_strtab = &shdrs[i];
    }
    if (!shdr_symtab)
    {
        fprintf(stderr, "no .symtab section\n");
        goto error;
    }
    if (!shdr_strtab)
    {
        fprintf(stderr, "no .strtab section\n");
        goto error;
    }
    if (shdr_symtab->sh_entsize != sizeof(Elf32_Sym) || !is_section_in_file(shdr_symtab, st.st_size))
    {
        fprintf(stderr, "bad .symtab section\n");
        goto error;
    }
    if (!is_string_table_in_file(shdr_strtab, f, st.st_size))
    {
        fprintf(stderr, "bad .strtab section\n");
        goto error;
    }

    const Elf32_Sym *symtab = (Elf32_Sym *)(f + shdr_symtab->sh_offset);
    const char *strtab = (const char *)(f + shdr_strtab->sh_offset);
    int num_syms = shdr_symtab->sh_size / shdr_symtab->sh_entsize;
    // The first pass checks every request and writes nothing, so a bad one leaves the file as it was.
    for (int pass = 0; pass < 2; pass++)
    {
        bool write = pass == 1;
        for (int j = 2; j < argc; j += 2)
        {
            const char *arg_name = argv[j + 0];
            const char *arg_value = argv[j + 1];
            bool found = false;
            for (int i = 0; i < num_syms; i++)
            {
                if (symtab[i].st_name == 0 || symtab[i].st_name >= shdr_strtab->sh_size) continue;
                if (strcmp(strtab + symtab[i].st_name, arg_name) != 0) continue;
                char *value = find_symbol_data(arg_name, ehdr, shdrs, &symtab[i], f, st.st_size);
                if (value == NULL)
                    goto error;
                if (!try_patch_value(arg_name, write ? value : NULL, arg_value, symtab[i].st_size))
                    goto error;
                found = true;
            }
            if (!found)
            {
                fprintf(stderr, "%s: symbol not found\n", arg_name);
                goto error;
            }
        }
    }

    exit_code = 0;

error:
    if (f != MAP_FAILED)
    {
        if (msync(f, st.st_size, MS_SYNC) == -1)
        {
            perror("msync failed");
            f = MAP_FAILED;
        }
    }
    if (f != MAP_FAILED)
    {
        if (munmap(f, st.st_size) == -1)
        {
            perror("munmap failed");
        }
    }
    if (fd != -1)
    {
        if (close(fd) == -1)
        {
            perror("close failed");
        }
    }

    return exit_code;
}

static bool is_section_in_file(const Elf32_Shdr *shdr, off_t file_size)
{
    return shdr->sh_offset <= file_size && shdr->sh_size <= file_size - shdr->sh_offset;
}

// A string table has to end in a NUL, so no name read from it runs past it.
static bool is_string_table_in_file(const Elf32_Shdr *shdr, const char *f, off_t file_size)
{
    return is_section_in_file(shdr, file_size) && shdr->sh_size > 0 && f[shdr->sh_offset + shdr->sh_size - 1] == '\0';
}

// Returns where the symbol's bytes are in the file, or NULL (with a message) when it has none
// there: no section, a section with no file data (.bss), or a range outside the section or file.
static char *find_symbol_data(const char *sym, const Elf32_Ehdr *ehdr, const Elf32_Shdr *shdrs, const Elf32_Sym *symbol, char *f, off_t file_size)
{
    if (symbol->st_shndx == SHN_UNDEF || symbol->st_shndx >= ehdr->e_shnum)
    {
        fprintf(stderr, "%s: symbol has no section (index %u)\n", sym, symbol->st_shndx);
        return NULL;
    }
    const Elf32_Shdr *shdr = &shdrs[symbol->st_shndx];
    if (shdr->sh_type == SHT_NOBITS)
    {
        fprintf(stderr, "%s: symbol's section has no data in the file (SHT_NOBITS, such as .bss)\n", sym);
        return NULL;
    }
    if (symbol->st_value < shdr->sh_addr
     || symbol->st_value - shdr->sh_addr > shdr->sh_size
     || symbol->st_size > shdr->sh_size - (symbol->st_value - shdr->sh_addr))
    {
        fprintf(stderr, "%s: symbol lies outside its section\n", sym);
        return NULL;
    }
    if (!is_section_in_file(shdr, file_size))
    {
        fprintf(stderr, "%s: symbol's section lies outside the file\n", sym);
        return NULL;
    }
    return f + shdr->sh_offset + (symbol->st_value - shdr->sh_addr);
}

static int parsexdigit(char c)
{
    if ('0' <= c && c <= '9')
        return c - '0';
    else if ('a' <= c && c <= 'f')
        return c - 'a' + 10;
    else if ('A' <= c && c <= 'F')
        return c - 'A' + 10;
    else
        return -1;
}

static bool try_patch_value(const char *sym, char *dest, const char *source, size_t size)
{
    int i = 0;
    while (*source)
    {
        if (i == size)
        {
            fprintf(stderr, "%s: overflows size (%zu)\n", sym, size);
            return false;
        }
        char c, value;
        switch ((c = *source++))
        {
        case '\\':
            switch ((c = *source++))
            {
            case '0':
                value = 0;
                break;
            case 'x':
                if (!isxdigit((unsigned char)(c = *source++)))
                {
                    fprintf(stderr, "%s: illegal escape \\x%c\n", sym, c);
                    return false;
                }
                value = parsexdigit(c);
                if (!isxdigit((unsigned char)(c = *source++)))
                {
                    fprintf(stderr, "%s: illegal escape \\x%c%c\n", sym, *(source - 2), c);
                    return false;
                }
                value = value * 16 + parsexdigit(c);
                break;
            default:
                fprintf(stderr, "%s: illegal escape \\%c\n", sym, c);
                return false;
            }
            break;
        default:
            value = c;
            break;
        }
        if (dest != NULL)
            dest[i] = value;
        i++;
    }
    return true;
}
