// Schema do Sanity Studio para posts gerados pelo Blog AI da Voruto.
// Adicione este arquivo em seu projeto Sanity em: schemas/blogPost.js
// e inclua no schemas/index.js: import blogPost from './blogPost'

export default {
  name: 'blogPost',
  title: 'Blog Post',
  type: 'document',

  fields: [
    {
      name: 'title',
      title: 'Título',
      type: 'string',
      validation: Rule => Rule.required(),
    },
    {
      name: 'slug',
      title: 'Slug',
      type: 'slug',
      options: { source: 'title', maxLength: 80 },
      validation: Rule => Rule.required(),
    },
    {
      name: 'publishedAt',
      title: 'Publicado em',
      type: 'datetime',
      options: { dateFormat: 'DD/MM/YYYY', timeFormat: 'HH:mm' },
    },
    {
      name: 'category',
      title: 'Categoria',
      type: 'string',
      options: {
        list: [
          { title: 'Lançamentos TCG',          value: 'Lançamentos TCG' },
          { title: 'Leilões & Mercado',         value: 'Leilões & Mercado' },
          { title: 'Collabs & Cultura',         value: 'Collabs & Cultura' },
          { title: 'Guia do Colecionador',      value: 'Guia do Colecionador' },
          { title: 'Curiosidades & Raridades',  value: 'Curiosidades & Raridades' },
          { title: 'Mercado Global',            value: 'Mercado Global' },
        ],
      },
    },
    {
      name: 'excerpt',
      title: 'Resumo',
      type: 'text',
      rows: 3,
    },
    {
      name: 'contentHtml',
      title: 'Conteúdo (HTML)',
      type: 'text',
      rows: 25,
      description: 'HTML gerado automaticamente pelo Blog AI. Edite aqui para revisão antes de publicar.',
    },
    {
      name: 'metaDescription',
      title: 'Meta Description (SEO)',
      type: 'string',
      validation: Rule => Rule.max(155).warning('Máximo recomendado: 155 caracteres'),
    },
    {
      name: 'tags',
      title: 'Tags',
      type: 'array',
      of: [{ type: 'string' }],
      options: { layout: 'tags' },
    },
    {
      name: 'aiGenerated',
      title: 'Gerado por IA',
      type: 'boolean',
      initialValue: true,
      readOnly: true,
    },
  ],

  orderings: [
    {
      title: 'Mais recentes',
      name: 'publishedAtDesc',
      by: [{ field: 'publishedAt', direction: 'desc' }],
    },
  ],

  preview: {
    select: {
      title:    'title',
      subtitle: 'category',
      date:     'publishedAt',
    },
    prepare({ title, subtitle, date }) {
      const d = date ? new Date(date).toLocaleDateString('pt-BR') : '—'
      return { title, subtitle: `${subtitle || '—'}  ·  ${d}` }
    },
  },
}
